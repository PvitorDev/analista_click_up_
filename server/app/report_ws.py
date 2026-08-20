from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.chat import _session_from_ws
from app.config import settings
from app.db import execute

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_session_member(session: dict) -> str:
    uid = str(session.get("clickup_user_id") or "")
    if not uid:
        return ""
    execute(
        """
        INSERT INTO members (clickup_id, username, display_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (clickup_id) DO UPDATE SET
            username = COALESCE(members.username, EXCLUDED.username),
            display_name = COALESCE(members.display_name, EXCLUDED.display_name),
            updated_at = now()
        """,
        (
            uid,
            session.get("username") or None,
            session.get("username") or None,
        ),
    )
    return uid


@router.websocket("/ws/reports/generate")
async def generate_report_ws(websocket: WebSocket):
    await websocket.accept()
    session = _session_from_ws(websocket)
    if not session:
        await websocket.send_json({"type": "error", "detail": "Sessão ausente ou expirada"})
        await websocket.close(code=4401)
        return

    if not settings.anthropic_api_key:
        await websocket.send_json({"type": "error", "detail": "ANTHROPIC_API_KEY ausente"})
        await websocket.close(code=1008)
        return

    from app.agent import _prepare_bundle, parse_report_output, persist_generated, stream_report_llm
    from app.clickup.cache import cache_clear_all
    from app.sync.engine import run_sync
    from app.workspace import current_team_id, last_sync_fresh

    try:
        uid = _ensure_session_member(session)
        await websocket.send_json({"type": "phase", "value": "sync"})
        team_id = current_team_id()
        if last_sync_fresh(team_id, minutes=10):
            pass
        else:
            await asyncio.to_thread(run_sync, deep=False, use_cache=True)

        await websocket.send_json({"type": "phase", "value": "writing"})
        bundle = _prepare_bundle(uid or None)

        async def on_delta(piece: str) -> None:
            await websocket.send_json({"type": "narrative_delta", "content": piece})

        raw = await stream_report_llm(bundle, on_delta)
        parsed = parse_report_output(raw)
        saved = persist_generated(parsed, uid or None)
        cache_clear_all()
        await websocket.send_json(
            {
                "type": "done",
                "report_id": saved["id"],
                "title": saved.get("title"),
            }
        )
    except WebSocketDisconnect:
        return
    except RuntimeError as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
    except Exception:
        logger.exception("Falha no WS /ws/reports/generate")
        try:
            await websocket.send_json(
                {"type": "error", "detail": "Falha ao gerar relatório."}
            )
        except Exception:
            return
    finally:
        try:
            await websocket.close()
        except Exception:
            return
