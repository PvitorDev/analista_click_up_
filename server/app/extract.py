from __future__ import annotations

import re
from datetime import datetime

from app.db import execute, fetch_all
from app.status_map import AREA_PREFIXES, _norm, taxonomy_from_title


DATE_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?")
HANDOFF_RE = re.compile(
    r"(handoff|depende|n[aã]o come[cç]a sem|bloquead[oa] por|espera(?:r)?|aguardando|waiting on|blocked by)\s*[:\-]?\s*(.+)",
    re.I,
)
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
CLICKUP_URL_RE = re.compile(
    r"https?://(?:app\.)?clickup\.com/t/(?:[0-9]+/)?([A-Za-z0-9_-]+)",
    re.I,
)
DE_PARA_RE = re.compile(
    r"\bde\s+(.+?)\s+(?:para|p/|->|→)\s+(.+)$",
    re.I,
)
_NAME_STOP = {
    "de", "da", "do", "para", "por", "com", "sem", "handoff", "task", "card",
    "equipe", "time", "team", "espera", "esperar", "depende", "bloqueado",
    "bloqueada", "aguardando",
}


def _parse_date(text: str):
    m = DATE_RE.search(text or "")
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
    year = datetime.now().year if not y else int(y)
    if year < 100:
        year += 2000
    try:
        return datetime(year, mo, d).date()
    except ValueError:
        try:
            return datetime(year, d, mo).date()
        except ValueError:
            return None


def _token_in_text(hay: str, needle: str) -> bool:
    if not needle:
        return False
    return re.search(r"(?<![a-z0-9_])" + re.escape(needle) + r"(?![a-z0-9_])", hay, re.I) is not None


def _resolve_to_task(line: str, source_id: str, catalog: list[dict]) -> str | None:
    """Um destino explícito e único; ambíguo ou ausente → None (não inventa)."""
    explicit: set[str] = set()
    by_id = {str(t["clickup_id"]): t for t in catalog}
    by_id_lower = {i.lower(): i for i in by_id}
    custom_map: dict[str, set[str]] = {}
    for t in catalog:
        custom = (t.get("custom_id") or "").strip().lower()
        if custom:
            custom_map.setdefault(custom, set()).add(str(t["clickup_id"]))

    def _add_custom(token: str) -> None:
        ids = custom_map.get(token.lower()) or set()
        if len(ids) == 1:
            explicit.add(next(iter(ids)))
        elif len(ids) > 1:
            explicit.update(ids)

    for token in CLICKUP_URL_RE.findall(line or ""):
        if token.lower() in by_id_lower:
            explicit.add(by_id_lower[token.lower()])
        else:
            _add_custom(token)

    hay = line or ""
    for tid in by_id:
        if tid != source_id and _token_in_text(hay, tid):
            explicit.add(tid)
    for custom in custom_map:
        if _token_in_text(hay, custom):
            _add_custom(custom)

    explicit.discard(source_id)
    if len(explicit) == 1:
        return next(iter(explicit))
    if len(explicit) > 1:
        return None

    title_hits: set[str] = set()
    ranked = sorted(
        (
            (t.get("name") or "").strip(),
            str(t["clickup_id"]),
        )
        for t in catalog
        if t["clickup_id"] != source_id and (t.get("name") or "").strip()
    )
    ranked.sort(key=lambda row: len(row[0]), reverse=True)
    for name, tid in ranked:
        if len(name) < 4:
            continue
        if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", hay, re.I):
            title_hits.add(tid)
    if len(title_hits) == 1:
        return next(iter(title_hits))
    return None


def _member_mentions(text: str, members: list[dict]) -> list[str]:
    hay = _norm(text)
    occupied = [False] * len(hay)
    aliases: list[tuple[int, str, str]] = []
    for member in members:
        mid = str(member["clickup_id"])
        names = []
        for raw in (member.get("display_name"), member.get("username")):
            n = _norm(raw or "")
            if len(n) >= 3:
                names.append(n)
        local = _norm((member.get("email") or "").split("@")[0])
        if len(local) >= 4:
            names.append(local)
        for n in set(names):
            if n not in _NAME_STOP:
                aliases.append((len(n), n, mid))
    aliases.sort(reverse=True)
    found: list[str] = []
    seen: set[str] = set()
    for _, alias, mid in aliases:
        if mid in seen:
            continue
        start = 0
        while True:
            idx = hay.find(alias, start)
            if idx < 0:
                break
            end = idx + len(alias)
            left_ok = idx == 0 or not hay[idx - 1].isalnum()
            right_ok = end == len(hay) or not hay[end].isalnum()
            if left_ok and right_ok and not any(occupied[idx:end]):
                occupied[idx:end] = [True] * (end - idx)
                found.append(mid)
                seen.add(mid)
                break
            start = idx + 1
    return found


def _unique_member(text: str, members: list[dict]) -> str | None:
    hits = _member_mentions(text, members)
    return hits[0] if len(hits) == 1 else None


def _resolve_people(line: str, members: list[dict]) -> tuple[str | None, str | None]:
    """from_person, to_person a partir de nomes conhecidos. Ambíguo → NULL."""
    de_para = DE_PARA_RE.search(line or "")
    if de_para:
        src = _unique_member(de_para.group(1), members)
        dst = _unique_member(de_para.group(2), members)
        if src and dst and src != dst:
            return src, dst
        if dst and not src:
            return None, dst
        if src and not dst:
            return src, None
        return None, None

    hits = _member_mentions(line or "", members)
    if len(hits) == 1:
        return None, hits[0]
    return None, None


def _is_handoff_line(line: str) -> bool:
    low = line.lower()
    return bool(
        HANDOFF_RE.search(line)
        or "handoff" in low
        or "não começa" in low
        or "nao comeca" in low
        or "aguardando" in low
    )


def extract_from_tasks() -> dict:
    tasks = fetch_all(
        "SELECT clickup_id, name, description, assignees FROM tasks WHERE parent_id IS NULL"
    )
    catalog = fetch_all("SELECT clickup_id, name, custom_id, url FROM tasks")
    members = fetch_all("SELECT clickup_id, username, display_name, email FROM members")
    comments = fetch_all(
        "SELECT clickup_id, task_id, author_id, text, date FROM comments ORDER BY date"
    )
    by_task: dict[str, list] = {}
    for c in comments:
        by_task.setdefault(c["task_id"], []).append(c)

    counts = {"milestones": 0, "dependencies": 0, "risks": 0, "decisions": 0, "taxonomy": 0}

    for task in tasks:
        tid = task["clickup_id"]
        desc = task.get("description") or ""
        name = task.get("name") or ""
        area, tipo = taxonomy_from_title(name)
        if not area:
            lower = _norm(name + " " + desc[:500])
            for key, label in AREA_PREFIXES.items():
                if key in lower:
                    area = label
                    break
        if area or tipo:
            execute(
                """
                INSERT INTO task_taxonomy (task_id, area, tipo, source)
                VALUES (%s, %s, %s, 'content')
                ON CONFLICT (task_id) DO UPDATE SET
                    area = COALESCE(EXCLUDED.area, task_taxonomy.area),
                    tipo = COALESCE(EXCLUDED.tipo, task_taxonomy.tipo),
                    source = EXCLUDED.source
                """,
                (tid, area, tipo),
            )
            execute(
                "UPDATE tasks SET area = COALESCE(%s, area), tipo = COALESCE(%s, tipo) WHERE clickup_id = %s",
                (area, tipo, tid),
            )
            counts["taxonomy"] += 1

        for line in desc.splitlines():
            row = TABLE_ROW_RE.match(line)
            if row:
                cells = [c.strip() for c in row.group(1).split("|")]
                if len(cells) >= 2 and not set("".join(cells)) <= set("-: "):
                    phase = cells[0]
                    due = _parse_date(" ".join(cells[1:]))
                    if due or re.search(r"fase|etapa|sprint|marco", phase, re.I):
                        execute(
                            """
                            INSERT INTO milestones (task_id, phase, due_on, evidence)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (task_id, phase, due_on) DO NOTHING
                            """,
                            (tid, phase[:200], due, line.strip()[:500]),
                        )
                        counts["milestones"] += 1

            if _is_handoff_line(line):
                to_task = _resolve_to_task(line, tid, catalog)
                from_person, to_person = _resolve_people(line, members)
                execute(
                    """
                    INSERT INTO dependencies (
                        description, evidence_task_id, from_task_id, to_task_id, from_person, to_person
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (description, evidence_task_id) DO UPDATE SET
                        from_task_id = COALESCE(EXCLUDED.from_task_id, dependencies.from_task_id),
                        to_task_id = COALESCE(EXCLUDED.to_task_id, dependencies.to_task_id),
                        from_person = COALESCE(EXCLUDED.from_person, dependencies.from_person),
                        to_person = COALESCE(EXCLUDED.to_person, dependencies.to_person)
                    """,
                    (line.strip()[:1000], tid, tid, to_task, from_person, to_person),
                )
                counts["dependencies"] += 1

        in_risk = False
        kind = "risco"
        for line in desc.splitlines():
            header = _norm(line)
            if "risco" in header or "pendenc" in header or "⚠️" in line or "pendência" in header:
                in_risk = True
                kind = "pendencia" if "pendenc" in header else "risco"
                continue
            if in_risk and line.strip().startswith("#"):
                in_risk = False
            if in_risk and line.strip() and not line.strip().startswith("|"):
                execute(
                    """
                    INSERT INTO risks (task_id, kind, text)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (task_id, kind, text) DO NOTHING
                    """,
                    (tid, kind, line.strip()[:2000]),
                )
                counts["risks"] += 1

        for c in by_task.get(tid, []):
            text = c.get("text") or ""
            if _looks_like_decision(text):
                execute(
                    """
                    INSERT INTO decisions (task_id, comment_id, author_id, text, decided_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (task_id, comment_id) DO NOTHING
                    """,
                    (tid, c["clickup_id"], c.get("author_id"), text[:4000], c.get("date")),
                )
                counts["decisions"] += 1

    return counts


def collect_extraction_candidates() -> dict:
    """Candidatos heurísticos + trechos para refinamento LLM (somente leitura)."""
    tasks = fetch_all(
        """
        SELECT clickup_id, name, description
        FROM tasks
        WHERE parent_id IS NULL AND deleted_at IS NULL
          AND COALESCE(description, '') <> ''
        ORDER BY synced_at DESC
        LIMIT 30
        """
    )
    comments = fetch_all(
        """
        SELECT c.clickup_id, c.task_id, c.author_id, left(c.text, 500) AS text
        FROM comments c
        JOIN tasks t ON t.clickup_id = c.task_id
        WHERE t.parent_id IS NULL AND t.deleted_at IS NULL
        ORDER BY c.date DESC NULLS LAST
        LIMIT 80
        """
    )
    return {
        "tasks": tasks,
        "comments": comments,
        "milestones": fetch_all("SELECT task_id, phase, due_on, evidence FROM milestones ORDER BY id DESC LIMIT 40"),
        "dependencies": fetch_all(
            """
            SELECT description, evidence_task_id, from_task_id, to_task_id, from_person, to_person
            FROM dependencies ORDER BY id DESC LIMIT 40
            """
        ),
        "risks": fetch_all("SELECT task_id, kind, text FROM risks ORDER BY id DESC LIMIT 40"),
        "decisions": fetch_all(
            "SELECT task_id, comment_id, author_id, left(text, 400) AS text FROM decisions ORDER BY id DESC LIMIT 40"
        ),
        "task_catalog": fetch_all(
            "SELECT clickup_id, name, custom_id FROM tasks WHERE deleted_at IS NULL LIMIT 200"
        ),
        "members": fetch_all("SELECT clickup_id, username, display_name FROM members LIMIT 100"),
    }


def apply_refined_extraction(data: dict) -> dict:
    """Upsert enriquecido; nunca apaga extrações heurísticas."""
    counts = {"milestones": 0, "dependencies": 0, "risks": 0, "decisions": 0}
    for m in data.get("milestones") or []:
        task_id = m.get("task_id")
        phase = (m.get("phase") or "")[:200]
        if not task_id or not phase:
            continue
        execute(
            """
            INSERT INTO milestones (task_id, phase, due_on, evidence)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (task_id, phase, due_on) DO UPDATE SET
                evidence = COALESCE(EXCLUDED.evidence, milestones.evidence)
            """,
            (task_id, phase, m.get("due_on"), (m.get("evidence") or "")[:500]),
        )
        counts["milestones"] += 1

    for d in data.get("dependencies") or []:
        desc = (d.get("description") or "")[:1000]
        evidence = d.get("evidence_task_id")
        if not desc or not evidence:
            continue
        execute(
            """
            INSERT INTO dependencies (
                description, evidence_task_id, from_task_id, to_task_id, from_person, to_person
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (description, evidence_task_id) DO UPDATE SET
                from_task_id = COALESCE(EXCLUDED.from_task_id, dependencies.from_task_id),
                to_task_id = COALESCE(EXCLUDED.to_task_id, dependencies.to_task_id),
                from_person = COALESCE(EXCLUDED.from_person, dependencies.from_person),
                to_person = COALESCE(EXCLUDED.to_person, dependencies.to_person)
            """,
            (
                desc,
                evidence,
                d.get("from_task_id") or evidence,
                d.get("to_task_id"),
                d.get("from_person"),
                d.get("to_person"),
            ),
        )
        counts["dependencies"] += 1

    for r in data.get("risks") or []:
        task_id = r.get("task_id")
        text = (r.get("text") or "")[:2000]
        kind = r.get("kind") or "risco"
        if not task_id or not text:
            continue
        execute(
            """
            INSERT INTO risks (task_id, kind, text)
            VALUES (%s, %s, %s)
            ON CONFLICT (task_id, kind, text) DO NOTHING
            """,
            (task_id, kind, text),
        )
        counts["risks"] += 1

    for dec in data.get("decisions") or []:
        task_id = dec.get("task_id")
        comment_id = dec.get("comment_id")
        text = (dec.get("text") or "")[:4000]
        if not task_id or not comment_id or not text:
            continue
        execute(
            """
            INSERT INTO decisions (task_id, comment_id, author_id, text, decided_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (task_id, comment_id) DO UPDATE SET
                text = COALESCE(EXCLUDED.text, decisions.text),
                author_id = COALESCE(EXCLUDED.author_id, decisions.author_id)
            """,
            (task_id, comment_id, dec.get("author_id"), text, dec.get("decided_at")),
        )
        counts["decisions"] += 1

    return counts


async def run_llm_refine() -> dict:
    """Heurística já rodou; tenta enriquecer via LLM. Falha → só heurística."""
    from app.agent import refine_extraction_llm

    candidates = collect_extraction_candidates()
    try:
        parsed = await refine_extraction_llm(candidates)
        if not parsed:
            return {"refined": False, "counts": {}}
        counts = apply_refined_extraction(parsed)
        return {"refined": True, "counts": counts}
    except Exception:
        return {"refined": False, "counts": {}}


def _looks_like_decision(text: str) -> bool:
    if len(text) < 80:
        return False
    keys = ("decid", "vamos", "arquitetura", "pr ", "pull request", "optamos", "ficou definido", "acordo")
    low = _norm(text)
    return any(k in low for k in keys)
