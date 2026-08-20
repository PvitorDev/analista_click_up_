from __future__ import annotations

import json
import logging
import os
import re
import threading
from array import array
from datetime import datetime
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

INDEX = "rag_docs"
DOC_PREFIX = "doc:"
CHAT_KEEP = 20
KNN_K = 5
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384
CHUNK_CHARS = 700

_redis = None
_embedder = None
_embed_lock = threading.Lock()
_index_ready = False


def _client():
    global _redis
    if _redis is None:
        import redis

        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=False)
        _redis.ping()
    return _redis


def _str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _vec_bytes(values) -> bytes:
    return array("f", [float(x) for x in values]).tobytes()


def _embedder_model(*, wait: bool = True):
    global _embedder
    if _embedder is not None:
        return _embedder
    if not wait:
        return None
    with _embed_lock:
        if _embedder is not None:
            return _embedder
        from fastembed import TextEmbedding

        cache_dir = os.environ.get("FASTEMBED_CACHE_PATH") or None
        logger.info("Carregando modelo de embeddings %s", EMBED_MODEL)
        kwargs: dict[str, Any] = {"model_name": EMBED_MODEL}
        if cache_dir:
            kwargs["cache_dir"] = cache_dir
        _embedder = TextEmbedding(**kwargs)
        logger.info("Modelo de embeddings pronto")
        return _embedder


def embed_texts(texts: list[str], *, query: bool = False, wait: bool = True) -> list[bytes]:
    if not texts:
        return []
    model = _embedder_model(wait=wait)
    if model is None:
        return []
    vectors = list(model.embed([(t or "")[:4000] for t in texts]))
    return [_vec_bytes(v) for v in vectors]


def ensure_index() -> None:
    global _index_ready
    if _index_ready:
        return
    r = _client()
    from redis.commands.search.field import NumericField, TagField, TextField, VectorField
    from redis.commands.search.index_definition import IndexDefinition, IndexType

    try:
        r.ft(INDEX).info()
        _index_ready = True
        return
    except Exception:
        pass
    r.ft(INDEX).create_index(
        fields=[
            TagField("kind"),
            NumericField("report_id"),
            TextField("title"),
            TextField("text"),
            VectorField(
                "vector",
                "FLAT",
                {
                    "TYPE": "FLOAT32",
                    "DIM": EMBED_DIM,
                    "DISTANCE_METRIC": "COSINE",
                },
            ),
        ],
        definition=IndexDefinition(prefix=[DOC_PREFIX], index_type=IndexType.HASH),
    )
    _index_ready = True


def _chunk_text(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(r"\n\s*\n+", raw)
    chunks: list[str] = []
    buf = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if len(buf) + len(piece) + 1 <= CHUNK_CHARS:
            buf = f"{buf}\n{piece}".strip()
            continue
        if buf:
            chunks.append(buf)
        if len(piece) <= CHUNK_CHARS:
            buf = piece
        else:
            for i in range(0, len(piece), CHUNK_CHARS):
                chunks.append(piece[i : i + CHUNK_CHARS])
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks[:40]


def _improvements_text(improvements) -> str:
    if not improvements:
        return ""
    if isinstance(improvements, str):
        try:
            improvements = json.loads(improvements)
        except json.JSONDecodeError:
            return improvements
    lines: list[str] = []
    for item in improvements:
        if isinstance(item, dict):
            title = item.get("title") or item.get("change") or ""
            why = item.get("why") or item.get("reason") or item.get("detail") or ""
            lines.append(f"{title}: {why}".strip(": "))
        else:
            lines.append(str(item))
    return "\n".join(lines)


def set_report_meta(report_id: int, title: str, created_at: Any = None) -> None:
    try:
        r = _client()
        created = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or "")
        r.hset(
            f"report:{report_id}:meta".encode(),
            mapping={
                b"id": str(report_id).encode(),
                b"title": (title or "").encode(),
                b"created_at": created.encode(),
            },
        )
    except Exception:
        logger.exception("Falha ao gravar meta do relatório %s no Redis", report_id)


def index_report(report: dict) -> None:
    report_id = int(report["id"])
    title = report.get("title") or f"Relatório {report_id}"
    set_report_meta(report_id, title, report.get("created_at"))
    pieces = []
    if report.get("history_summary"):
        pieces.append(("resumo", str(report["history_summary"])))
    if report.get("narrative"):
        pieces.append(("diagnostico", str(report["narrative"])))
    imp = _improvements_text(report.get("improvements"))
    if imp:
        pieces.append(("mudancas", imp))

    chunks: list[tuple[str, str]] = []
    for label, body in pieces:
        for i, chunk in enumerate(_chunk_text(body)):
            chunks.append((f"{label}-{i}", chunk))
    if not chunks:
        return

    try:
        ensure_index()
        r = _client()
        old_key = f"report:{report_id}:chunks".encode()
        old = r.smembers(old_key)
        if old:
            r.delete(*old)
            r.delete(old_key)
        vectors = embed_texts([c[1] for c in chunks])
        pipe = r.pipeline()
        for (slug, text), vec in zip(chunks, vectors, strict=True):
            doc_key = f"{DOC_PREFIX}report:{report_id}:{slug}".encode()
            pipe.hset(
                doc_key,
                mapping={
                    b"kind": b"report",
                    b"report_id": str(report_id).encode(),
                    b"title": title.encode(),
                    b"text": text.encode(),
                    b"vector": vec,
                },
            )
            pipe.sadd(old_key, doc_key)
        pipe.execute()
    except Exception:
        logger.exception("Falha ao indexar relatório %s no Redis", report_id)


def reindex_reports_if_empty() -> None:
    try:
        ensure_index()
        info = _client().ft(INDEX).info()
        num = 0
        for key, val in info.items():
            name = key.decode() if isinstance(key, bytes) else str(key)
            if name == "num_docs":
                num = int(val)
                break
        if num > 0:
            return
    except Exception:
        logger.exception("Não foi possível ler o índice RAG")
        return
    from app.db import fetch_all

    from app.workspace import current_team_id

    team_id = current_team_id()
    if not team_id:
        return
    rows = fetch_all(
        """
        SELECT id, title, created_at, narrative, history_summary, improvements
        FROM reports
        WHERE team_id = %s
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (team_id,),
    )
    for row in rows:
        index_report(row)


def remember_user(session: dict) -> dict[str, str]:
    uid = str(session.get("clickup_user_id") or "")
    from app.db import fetch_one

    member = fetch_one(
        "SELECT display_name, username, email FROM members WHERE clickup_id = %s",
        (uid,),
    ) or {}
    profile = {
        "clickup_user_id": uid,
        "display_name": (
            member.get("display_name")
            or session.get("username")
            or uid
            or "usuário"
        ),
        "username": member.get("username") or session.get("username") or "",
        "email": member.get("email") or session.get("email") or "",
        "role": session.get("role") or "member",
    }
    try:
        r = _client()
        r.hset(
            f"user:{uid}".encode(),
            mapping={k.encode(): str(v).encode() for k, v in profile.items()},
        )
    except Exception:
        logger.exception("Falha ao gravar perfil do usuário no Redis")
    return profile


def _chat_key(user_id: str, report_id: int | None) -> bytes:
    scope = str(report_id) if report_id is not None else "global"
    return f"chat:{user_id}:{scope}".encode()


def append_chat(user_id: str, report_id: int | None, author: str, content: str) -> None:
    try:
        r = _client()
        key = _chat_key(user_id, report_id)
        payload = json.dumps(
            {"author": author, "content": content},
            ensure_ascii=False,
        ).encode()
        r.rpush(key, payload)
        r.ltrim(key, -CHAT_KEEP, -1)
    except Exception:
        logger.exception("Falha ao gravar mensagem no Redis")


def chat_history(user_id: str, report_id: int | None) -> list[dict[str, str]]:
    try:
        r = _client()
        rows = r.lrange(_chat_key(user_id, report_id), 0, -1)
    except Exception:
        logger.exception("Falha ao ler histórico Redis")
        return []
    out: list[dict[str, str]] = []
    for raw in rows:
        try:
            item = json.loads(_str(raw))
            out.append(
                {
                    "author": item.get("author") or "user",
                    "content": item.get("content") or "",
                }
            )
        except json.JSONDecodeError:
            continue
    return out


def search_reports(question: str, report_id: int | None = None, k: int = KNN_K) -> list[dict[str, str]]:
    if not question.strip():
        return []
    try:
        ensure_index()
        vecs = embed_texts([question], query=True, wait=False)
        if not vecs:
            return []
        vec = vecs[0]
        from redis.commands.search.query import Query

        if report_id is not None:
            expr = f"(@report_id:[{int(report_id)} {int(report_id)}])=>[KNN {k} @vector $vec AS score]"
        else:
            expr = f"*=>[KNN {k} @vector $vec AS score]"
        query = (
            Query(expr)
            .return_fields("text", "title", "report_id", "score")
            .paging(0, k)
            .dialect(2)
        )
        res = _client().ft(INDEX).search(query, query_params={"vec": vec})
    except Exception:
        logger.exception("Busca RAG falhou")
        return []
    hits: list[dict[str, str]] = []
    for doc in res.docs:
        hits.append(
            {
                "report_id": _str(getattr(doc, "report_id", "")),
                "title": _str(getattr(doc, "title", "")),
                "text": _str(getattr(doc, "text", "")),
            }
        )
    return hits


def compact_metrics() -> dict[str, Any]:
    from app.api import _jsonable
    from app.db import fetch_all, fetch_one
    from app.status_map import STATUS_LABEL_PT

    top = fetch_one("SELECT * FROM v_bottleneck LIMIT 1")
    wip_rows = fetch_all("SELECT display_name, wip FROM v_wip ORDER BY wip DESC LIMIT 8")
    hygiene_n = fetch_one(
        "SELECT count(*) AS n FROM v_hygiene WHERE cardinality(issues) > 0"
    )
    if top:
        status = STATUS_LABEL_PT.get(top.get("status_canonical"), top.get("status_canonical"))
        gargalo = {
            "status": status,
            "lista": top.get("list_name"),
            "dias_acumulados": top.get("dias_acumulados"),
        }
    else:
        gargalo = None
    return _jsonable(
        {
            "gargalo_1": gargalo,
            "trabalho_em_paralelo": wip_rows,
            "higiene_itens": int((hygiene_n or {}).get("n") or 0),
        }
    )


def focused_report(report_id: int | None) -> dict | None:
    from app.db import fetch_one
    from app.workspace import current_team_id

    team_id = current_team_id()
    if not team_id:
        return None
    if report_id is not None:
        row = fetch_one(
            """
            SELECT id,
                   COALESCE(NULLIF(title, ''), 'Relatório ' || to_char(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI')) AS title,
                   created_at
            FROM reports
            WHERE id = %s AND team_id = %s
            """,
            (report_id, team_id),
        )
        if row:
            return row
    return fetch_one(
        """
        SELECT id,
               COALESCE(NULLIF(title, ''), 'Relatório ' || to_char(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI')) AS title,
               created_at
        FROM reports
        WHERE team_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (team_id,),
    )


def build_prompt_context(
    session: dict,
    question: str,
    report_id: int | None,
) -> tuple[dict[str, str], str, list[dict[str, str]]]:
    profile = remember_user(session)
    report = focused_report(report_id)
    focus_id = int(report["id"]) if report else None
    hits = search_reports(question, focus_id)
    history = chat_history(str(session.get("clickup_user_id") or ""), focus_id)
    metrics = compact_metrics()
    from app.api import _jsonable

    created = report.get("created_at") if report else None
    if isinstance(created, datetime):
        created = created.isoformat()
    payload = {
        "usuario": {
            "nome": profile.get("display_name"),
            "username": profile.get("username"),
            "papel": profile.get("role"),
        },
        "relatorio_em_foco": _jsonable(
            {
                "id": report.get("id") if report else None,
                "titulo": report.get("title") if report else None,
                "criado_em": created,
            }
        )
        if report
        else None,
        "trechos_recuperados": hits,
        "metricas_resumo": metrics,
        "pergunta": question,
    }
    raw = json.dumps(payload, default=str, ensure_ascii=False)
    if len(raw) > 40000:
        raw = raw[:40000]
    return profile, raw, history


def _warmup_embedder() -> None:
    try:
        _embedder_model()
        reindex_reports_if_empty()
    except Exception:
        logger.exception("Warmup do modelo de embeddings falhou")


def boot() -> None:
    try:
        _client()
        ensure_index()
        logger.info("RAG Redis pronto")
    except Exception:
        logger.exception("RAG Redis indisponível no boot — chat segue sem índice")
    threading.Thread(
        target=_warmup_embedder, name="fastembed-warmup", daemon=True
    ).start()
