from __future__ import annotations

import json

from app.config import settings
from app.db import execute, fetch_one


def persist_team(team_id: str, team_name: str) -> None:
    if not team_id:
        return
    payload = json.dumps({"id": str(team_id), "name": team_name or team_id})
    execute(
        """
        INSERT INTO sync_state (key, value) VALUES ('selected_team_id', %s::jsonb)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """,
        (payload,),
    )
    execute(
        """
        INSERT INTO sync_state (key, value) VALUES ('resolved_team_id', %s::jsonb)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """,
        (payload,),
    )


def selected_team() -> dict | None:
    row = fetch_one("SELECT value FROM sync_state WHERE key = 'selected_team_id'")
    if not row:
        row = fetch_one("SELECT value FROM sync_state WHERE key = 'resolved_team_id'")
    value = (row or {}).get("value")
    if isinstance(value, dict) and value.get("id"):
        return {"id": str(value["id"]), "name": str(value.get("name") or value["id"])}
    if isinstance(value, str) and value:
        return {"id": value, "name": value}
    return None


def preferred_team_id() -> str:
    stored = selected_team()
    if stored:
        return stored["id"]
    return (settings.clickup_team_id or "").strip()


def current_team_id() -> str:
    return preferred_team_id()


def backfill_report_team_ids() -> None:
    tid = current_team_id()
    if not tid:
        return
    execute(
        "UPDATE reports SET team_id = %s WHERE team_id IS NULL OR team_id = ''",
        (tid,),
    )


def last_sync_is_team(team_id: str) -> bool:
    """True se o Postgres já está no workspace pedido (não precisa resincronizar)."""
    if not team_id:
        return False
    row = fetch_one("SELECT value FROM sync_state WHERE key = 'last_sync'")
    if not row:
        return False
    value = row.get("value") or {}
    stats = value.get("stats") if isinstance(value, dict) else {}
    return str((stats or {}).get("team_id") or "") == str(team_id)


def last_sync_fresh(team_id: str, minutes: int = 10) -> bool:
    from datetime import datetime, timezone

    if not team_id:
        return False
    row = fetch_one("SELECT value, updated_at FROM sync_state WHERE key = 'last_sync'")
    if not row:
        return False
    value = row.get("value") or {}
    stats = value.get("stats") if isinstance(value, dict) else {}
    if str((stats or {}).get("team_id") or "") != str(team_id):
        return False
    updated = row.get("updated_at")
    if not updated:
        return False
    if isinstance(updated, str):
        try:
            updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except ValueError:
            return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - updated).total_seconds() < minutes * 60


def team_from_list(teams: list[dict], team_id: str | None) -> tuple[str, str] | None:
    wanted = (team_id or "").strip()
    if not wanted:
        return None
    for team in teams:
        if str(team.get("id")) == wanted:
            return wanted, str(team.get("name") or wanted)
    return None


def ensure_default_team(teams: list[dict]) -> tuple[str, str]:
    """Usa a escolha salva, senão o .env, senão o primeiro workspace da lista."""
    match = team_from_list(teams, preferred_team_id())
    if match:
        current = selected_team()
        if not current or current["id"] != match[0]:
            persist_team(*match)
        backfill_report_team_ids()
        return match
    if not teams:
        return "", ""
    team = teams[0]
    pair = str(team["id"]), str(team.get("name") or team["id"])
    persist_team(*pair)
    backfill_report_team_ids()
    return pair
