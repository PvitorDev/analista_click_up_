from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
import httpx

from app.clickup.client import ClickUpClient, ClickUpError, service_client
from app.config import settings
from app.db import execute, fetch_one

router = APIRouter(prefix="/auth", tags=["auth"])

CLICKUP_AUTHORIZE = "https://app.clickup.com/api"
CLICKUP_TOKEN = "https://api.clickup.com/api/v2/oauth/token"


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": "/",
        "max_age": settings.session_ttl_hours * 3600,
    }


def normalize_role(role_raw) -> str:
    """Owner=1, Admin=2 → admin. Qualquer ausência vira member — nunca assumir admin."""
    try:
        role_int = int(role_raw)
    except (TypeError, ValueError):
        return "member"
    if role_int in (1, 2):
        return "admin"
    return "member"


def role_from_teams_payload(payload: dict, user_id: str, team_id: str) -> str:
    """Papel no workspace selecionado. Sem team_id, não assume admin pelo primeiro item da lista."""
    from app.workspace import preferred_team_id

    configured = (team_id or "").strip() or preferred_team_id()

    matches: list[str] = []
    for team in payload.get("teams") or []:
        if configured and str(team.get("id")) != configured:
            continue
        for member in team.get("members") or []:
            user = member.get("user") or {}
            uid = str(user.get("id") or member.get("id") or "")
            if uid != str(user_id):
                continue
            # Campo role pode vir no member ou não existir no token de usuário comum.
            raw = member.get("role")
            if raw is None:
                raw = user.get("role")
            if raw is None:
                matches.append("member")
            else:
                matches.append(normalize_role(raw))
    if not matches:
        return "member"
    if configured or len(matches) == 1:
        return matches[0]
    # Vários workspaces sem id definido: só admin se for admin em todos. Nunca assumir pelo primeiro.
    if all(role == "admin" for role in matches):
        return "admin"
    return "member"


def get_session(request: Request) -> dict | None:
    sid = request.cookies.get(settings.session_cookie_name)
    if not sid:
        return None
    row = fetch_one(
        "SELECT * FROM sessions WHERE id = %s AND expires_at > now()",
        (sid,),
    )
    return row


def require_session(request: Request) -> dict:
    if settings.dev_bypass_auth and not settings.is_production:
        return {
            "id": "dev",
            "clickup_user_id": request.headers.get("x-dev-user-id", "dev-user"),
            "role": request.headers.get("x-dev-role", "admin"),
            "username": "dev",
        }
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Sessão ausente ou expirada")
    return session


def _identity_from_client(cu: ClickUpClient) -> tuple[dict, str]:
    from app.workspace import ensure_default_team

    payload = cu.authorized_user()
    user = payload.get("user") or payload
    user_id = str(user.get("id"))
    try:
        teams = cu.teams()
        team_id, _ = ensure_default_team(teams.get("teams") or [])
        role = role_from_teams_payload(teams, user_id, team_id)
    except ClickUpError:
        role = "member"
    return user, role


def _session_redirect(user: dict, role: str, access_token: str) -> RedirectResponse:
    session_id = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)
    execute(
        """
        INSERT INTO sessions (id, clickup_user_id, role, access_token, username, email, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            session_id,
            str(user.get("id")),
            role,
            access_token,
            user.get("username"),
            user.get("email"),
            expires,
        ),
    )
    response = RedirectResponse(url=f"{settings.frontend_url.rstrip('/')}/", status_code=302)
    response.set_cookie(settings.session_cookie_name, session_id, **_cookie_kwargs())
    return response


@router.get("/login")
def login():
    if settings.clickup_client_id:
        url = (
            f"{CLICKUP_AUTHORIZE}?client_id={settings.clickup_client_id}"
            f"&redirect_uri={settings.clickup_redirect_uri}"
        )
        return RedirectResponse(url)

    if settings.is_production:
        raise HTTPException(
            status_code=500,
            detail="CLICKUP_CLIENT_ID é obrigatório em produção (OAuth ClickUp).",
        )

    if not settings.clickup_api_token:
        raise HTTPException(
            status_code=500,
            detail="Sem CLICKUP_CLIENT_ID. Em desenvolvimento, defina CLICKUP_API_TOKEN ou registre um app OAuth.",
        )

    cu = service_client()
    user, role = _identity_from_client(cu)
    return _session_redirect(user, role, settings.clickup_api_token)


@router.get("/callback")
def callback(code: str | None = None):
    if not code:
        raise HTTPException(status_code=400, detail="code ausente")
    with httpx.Client(timeout=30.0) as client:
        token_resp = client.post(
            CLICKUP_TOKEN,
            params={
                "client_id": settings.clickup_client_id,
                "client_secret": settings.clickup_client_secret,
                "code": code,
            },
        )
        if token_resp.status_code >= 400:
            raise HTTPException(status_code=401, detail="Falha ao trocar code por token")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="Token ClickUp ausente")

        headers = {"Authorization": access_token}
        user_resp = client.get("https://api.clickup.com/api/v2/user", headers=headers)
        if user_resp.status_code >= 400:
            raise HTTPException(status_code=401, detail="Não foi possível ler o usuário ClickUp")
        user = user_resp.json().get("user") or user_resp.json()
        user_id = str(user.get("id"))

        team_resp = client.get("https://api.clickup.com/api/v2/team", headers=headers)
        if team_resp.status_code >= 400:
            role = "member"
        else:
            from app.workspace import ensure_default_team

            teams_payload = team_resp.json()
            team_id, _ = ensure_default_team(teams_payload.get("teams") or [])
            role = role_from_teams_payload(teams_payload, user_id, team_id)

    return _session_redirect(user, role, access_token)


@router.post("/logout")
def logout(request: Request, response: Response):
    sid = request.cookies.get(settings.session_cookie_name)
    if sid:
        execute("DELETE FROM sessions WHERE id = %s", (sid,))
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    session = require_session(request)
    return {
        "clickup_user_id": session["clickup_user_id"],
        "role": session["role"],
        "username": session.get("username"),
        "email": session.get("email"),
    }
