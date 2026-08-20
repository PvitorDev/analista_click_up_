from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.db import execute, fetch_one

logger = logging.getLogger(__name__)

router = APIRouter()

CHAT_SYSTEM = """Você é o analista sênior deste workspace ClickUp, em conversa.
Responda em português claro, para um gestor (não engenheiro).

A última mensagem do usuário é a pergunta. Responda ELA — não o bloco de contexto.
O contexto (quem é o usuário, relatório, trechos, métricas) é só apoio. Não resuma o relatório se ninguém pediu.
Se perguntarem o nome, use usuario.nome (ou username) do contexto e responda em uma frase.
Se não souber: diga que não está no relatório/métricas. NÃO invente números. NÃO escreva no ClickUp.

Quando citar card, use o NOME do card, nunca o id. Status em português (A fazer, Em andamento…), nunca A_FAZER.
Não use nomes de campo (lead_mediana, WIP, bus_factor). Traduza: tempo da criação até concluir; trabalho em paralelo; etc.

Formato Markdown (obrigatório quando houver seções):
- Títulos com ## ou ### (nunca deixe o # solto no meio de um parágrafo)
- **negrito**, *itálico*, listas com "- " ou "1. "
- Separador --- só entre seções
Não devolva JSON.
"""

MEMBER_RULE = (
    "O usuário é member: NÃO ranqueie pessoas por desempenho; "
    "não compare colaboradores; pode falar de processo (gargalo, WIP agregado, aging)."
)
ADMIN_RULE = (
    "O usuário é admin: pode citar pessoas que já aparecem no resumo de métricas. "
    "Não busque perfis individuais que não estejam no payload."
)


def _session_from_ws(websocket: WebSocket) -> dict | None:
    if settings.dev_bypass_auth and not settings.is_production:
        return {
            "id": "dev",
            "clickup_user_id": websocket.query_params.get("dev_user")
            or websocket.headers.get("x-dev-user-id", "dev-user"),
            "role": websocket.query_params.get("dev_role")
            or websocket.headers.get("x-dev-role", "admin"),
            "username": "dev",
        }
    sid = websocket.cookies.get(settings.session_cookie_name)
    if not sid:
        return None
    return fetch_one(
        "SELECT * FROM sessions WHERE id = %s AND expires_at > now()",
        (sid,),
    )


def _parse_report_id(raw) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        rid = int(raw)
    except (TypeError, ValueError):
        return None
    from app.workspace import current_team_id

    team_id = current_team_id()
    if team_id and fetch_one(
        "SELECT id FROM reports WHERE id = %s AND team_id = %s",
        (rid, team_id),
    ):
        return rid
    return None


def _save_message(user_id: str, author: str, content: str, report_id: int | None) -> None:
    try:
        execute(
            """
            INSERT INTO chat_messages (clickup_user_id, author, content, report_id)
            VALUES (%s, %s, %s, %s)
            """,
            (str(user_id), author, content, report_id),
        )
    except Exception:
        logger.exception("Falha ao persistir chat_messages")
    try:
        from app.rag import append_chat

        append_chat(str(user_id), report_id, author, content)
    except Exception:
        logger.exception("Falha ao persistir chat no Redis")


def _llm_messages(history: list[dict[str, str]], question: str) -> list[dict]:
    converted: list[dict[str, str]] = []
    q = (question or "").strip()
    for item in history or []:
        role = "assistant" if item.get("author") == "assistant" else "user"
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if converted and converted[-1]["role"] == role:
            converted[-1]["content"] += "\n" + content
        else:
            converted.append({"role": role, "content": content})
    if converted and converted[-1]["role"] == "user" and converted[-1]["content"] == q:
        converted.pop()
    if converted and converted[0]["role"] != "user":
        converted.insert(0, {"role": "user", "content": "(início da conversa)"})
    converted.append({"role": "user", "content": q})
    return converted


async def _stream_answer(
    websocket: WebSocket,
    session: dict,
    question: str,
    report_id: int | None,
) -> str:
    if not settings.anthropic_api_key:
        await websocket.send_json(
            {"type": "error", "detail": "ANTHROPIC_API_KEY ausente"}
        )
        return ""

    import anthropic
    from app.rag import build_prompt_context

    role = session.get("role") or "member"
    _, payload, history = build_prompt_context(session, question, report_id)
    system = (
        CHAT_SYSTEM
        + "\n"
        + (ADMIN_RULE if role == "admin" else MEMBER_RULE)
        + "\n\nCONTEXTO (não é a pergunta do usuário):\n"
        + payload
    )
    messages = _llm_messages(history, question)
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    chunks: list[str] = []
    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=2000,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    chunks.append(text)
                    await websocket.send_json({"type": "assistant_delta", "content": text})
        await websocket.send_json({"type": "assistant_done"})
    except Exception:
        logger.exception("Falha no stream do chat")
        if not chunks:
            try:
                msg = await client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=2000,
                    system=system,
                    messages=messages,
                )
                text = "".join(getattr(b, "text", "") or "" for b in msg.content)
                if text:
                    chunks.append(text)
                    await websocket.send_json({"type": "assistant_delta", "content": text})
                await websocket.send_json({"type": "assistant_done"})
            except Exception:
                logger.exception("Fallback Anthropic do chat também falhou")
                await websocket.send_json(
                    {"type": "error", "detail": "Falha ao gerar resposta do analista."}
                )
                return ""
        else:
            await websocket.send_json({"type": "assistant_done"})
    return "".join(chunks)


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    session = _session_from_ws(websocket)
    if not session:
        await websocket.send_json({"type": "error", "detail": "Sessão ausente ou expirada"})
        await websocket.close(code=4401)
        return

    from app.rag import remember_user

    profile = remember_user(session)
    role = profile.get("role") or session.get("role") or "member"
    await websocket.send_json(
        {
            "type": "hello",
            "role": role,
            "username": profile.get("username") or session.get("username"),
            "display_name": profile.get("display_name"),
        }
    )

    busy = False
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if msg_type != "user":
                continue
            content = str(data.get("content") or "").strip()
            if not content:
                await websocket.send_json({"type": "error", "detail": "Mensagem vazia"})
                continue
            if len(content) > 4000:
                content = content[:4000]
            if busy:
                await websocket.send_json({"type": "error", "detail": "Aguarde a resposta"})
                continue
            busy = True
            try:
                uid = str(session.get("clickup_user_id") or "")
                report_id = _parse_report_id(data.get("report_id"))
                _save_message(uid, "user", content, report_id)
                reply = await _stream_answer(websocket, session, content, report_id)
                if reply:
                    _save_message(uid, "assistant", reply, report_id)
            finally:
                busy = False
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("WebSocket /ws/chat encerrado com erro")
        try:
            await websocket.close(code=1011)
        except Exception:
            return
