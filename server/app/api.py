from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_session
from app.db import execute, fetch_all, fetch_one
from app.extract import extract_from_tasks
from app.guard import require_profile_access
from app.sync.engine import run_sync

def _page_args(page: int = 1, limit: int = 5) -> tuple[int, int]:
    limit = min(max(int(limit or 5), 1), 50)
    page = max(int(page or 1), 1)
    return page, limit


def _paged(sql: str, params: tuple = (), *, page: int = 1, limit: int = 5) -> dict:
    page, limit = _page_args(page, limit)
    offset = (page - 1) * limit
    rows = fetch_all(
        f"SELECT *, COUNT(*) OVER() AS _total FROM ({sql}) AS _page_src LIMIT %s OFFSET %s",
        (*params, limit, offset),
    )
    total = int(rows[0]["_total"]) if rows else 0
    items = []
    for row in rows:
        item = dict(row)
        item.pop("_total", None)
        items.append(item)
    return {"items": _jsonable(items), "total": total}


class WorkspaceSelect(BaseModel):
    team_id: str


def _jsonable(value):
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health():
    last = fetch_one("SELECT value, updated_at FROM sync_state WHERE key = 'last_sync'")
    return {"ok": True, "last_sync": _jsonable(last)}


@router.get("/workspaces")
def list_workspaces(session: dict = Depends(require_session)):
    from app.clickup.client import service_client
    from app.workspace import ensure_default_team

    teams = service_client().workspaces()
    selected_id, selected_name = ensure_default_team(teams)
    return {
        "workspaces": [
            {"id": str(t.get("id")), "name": t.get("name") or str(t.get("id"))}
            for t in teams
        ],
        "selected": {"id": selected_id, "name": selected_name} if selected_id else None,
    }


@router.post("/workspaces/select")
def select_workspace(body: WorkspaceSelect, session: dict = Depends(require_session)):
    from app.auth import role_from_teams_payload
    from app.clickup.client import service_client
    from app.workspace import last_sync_is_team, persist_team, team_from_list

    team_id = str(body.team_id or "").strip()
    if not team_id:
        raise HTTPException(status_code=400, detail="team_id ausente")
    client = service_client()
    payload = client.teams()
    teams = payload.get("teams") or []
    match = team_from_list(teams, team_id)
    if not match:
        raise HTTPException(status_code=400, detail="Workspace não autorizado neste token")
    persist_team(*match)
    try:
        role = role_from_teams_payload(
            payload, str(session.get("clickup_user_id") or ""), match[0]
        )
        if session.get("id") and session.get("id") != "dev":
            execute("UPDATE sessions SET role = %s WHERE id = %s", (role, session["id"]))
    except Exception:
        role = session.get("role") or "member"
    if last_sync_is_team(match[0]):
        sync_stats = {"skipped": True, "cached": True, "team_id": match[0]}
    else:
        sync_stats = run_sync(deep=False, use_cache=True)
    return _jsonable(
        {
            "selected": {"id": match[0], "name": match[1]},
            "role": role,
            "sync": sync_stats,
        }
    )


@router.get("/metrics/bottleneck")
def bottleneck(session: dict = Depends(require_session)):
    return _jsonable(fetch_all("SELECT * FROM v_bottleneck LIMIT 50"))


@router.get("/metrics/time-in-status")
def time_in_status(page: int = 1, limit: int = 5, session: dict = Depends(require_session)):
    return _paged(
        """
        SELECT DISTINCT ON (status_canonical)
               status_canonical, mediana_dias, p85_dias, n
        FROM v_time_in_status_stats
        WHERE list_id IS NULL AND area IS NULL AND person_id IS NULL
        ORDER BY status_canonical, n DESC
        """,
        page=page,
        limit=limit,
    )


@router.get("/metrics/wip")
def wip(session: dict = Depends(require_session)):
    return _jsonable(fetch_all("SELECT * FROM v_wip"))


@router.get("/metrics/aging")
def aging(page: int = 1, limit: int = 5, session: dict = Depends(require_session)):
    payload = _paged(
        "SELECT * FROM v_aging ORDER BY days_in_status DESC",
        page=page,
        limit=limit,
    )
    stale = fetch_one("SELECT count(*) AS n FROM v_aging WHERE aging_bucket >= 30")
    payload["stale_30"] = int((stale or {}).get("n") or 0)
    return payload


@router.get("/metrics/lead-cycle")
def lead_cycle(page: int = 1, limit: int = 5, session: dict = Depends(require_session)):
    return _paged(
        """
        SELECT list_name, area, prioridade,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lead_days) AS lead_mediana,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY cycle_days) AS cycle_mediana,
               count(*) AS n
        FROM v_lead_cycle
        GROUP BY list_name, area, prioridade
        ORDER BY n DESC
        """,
        page=page,
        limit=limit,
    )


@router.get("/metrics/rework")
def rework(session: dict = Depends(require_session)):
    return _jsonable(fetch_all("SELECT * FROM v_rework ORDER BY returns_from_review DESC"))


@router.get("/metrics/hygiene")
def hygiene(page: int = 1, limit: int = 5, session: dict = Depends(require_session)):
    return _paged(
        """
        SELECT * FROM v_hygiene
        WHERE cardinality(issues) > 0
        ORDER BY task_id
        """,
        page=page,
        limit=limit,
    )


@router.get("/metrics/duplicates")
def duplicates(page: int = 1, limit: int = 5, session: dict = Depends(require_session)):
    return _paged(
        "SELECT * FROM v_possible_duplicates ORDER BY task_a, task_b",
        page=page,
        limit=limit,
    )


@router.get("/metrics/block-chain")
def block_chain(page: int = 1, limit: int = 5, session: dict = Depends(require_session)):
    return _paged(
        "SELECT * FROM v_block_chain ORDER BY days_blocked DESC NULLS LAST, id",
        page=page,
        limit=limit,
    )


@router.get("/metrics/promised")
def promised(page: int = 1, limit: int = 5, session: dict = Depends(require_session)):
    return _paged(
        "SELECT * FROM v_promised_vs_delivered ORDER BY id",
        page=page,
        limit=limit,
    )


@router.get("/task-catalog")
def task_catalog(session: dict = Depends(require_session)):
    from app.clickup.cache import cached_json
    from app.workspace import current_team_id

    team_id = current_team_id()

    def build():
        return _jsonable(
            fetch_all(
                """
                SELECT clickup_id, custom_id, name, url, status_canonical, status_raw
                FROM tasks
                WHERE deleted_at IS NULL AND parent_id IS NULL
                ORDER BY name
                LIMIT 500
                """
            )
        )

    return cached_json(f"api:catalog:{team_id}", build)


@router.get("/tasks/{task_id}")
def task_detail(task_id: str, session: dict = Depends(require_session)):
    task = fetch_one("SELECT * FROM tasks WHERE clickup_id = %s", (task_id,))
    if not task:
        raise HTTPException(status_code=404, detail="Não encontrado")
    comments = fetch_all(
        "SELECT clickup_id, author_id, text, date FROM comments WHERE task_id = %s ORDER BY date",
        (task_id,),
    )
    transitions = fetch_all(
        "SELECT from_status, to_status, from_canonical, to_canonical, at, source FROM status_transitions WHERE task_id = %s ORDER BY at",
        (task_id,),
    )
    return _jsonable({"task": task, "comments": comments, "transitions": transitions})


@router.get("/reports")
def list_reports(session: dict = Depends(require_session)):
    from app.clickup.cache import cached_json
    from app.workspace import current_team_id

    team_id = current_team_id()

    def build():
        rows = fetch_all(
            """
            SELECT id,
                   COALESCE(NULLIF(title, ''), 'Relatório ' || to_char(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI')) AS title,
                   created_at
            FROM reports
            WHERE team_id = %s
            ORDER BY created_at DESC
            """,
            (team_id,),
        )
        return _jsonable(rows)

    return cached_json(f"api:reports:{team_id}", build)


@router.get("/reports/latest")
def latest_report(session: dict = Depends(require_session)):
    from app.clickup.cache import cached_json
    from app.workspace import current_team_id

    team_id = current_team_id()

    def build():
        report = fetch_one(
            """
            SELECT *,
                   COALESCE(NULLIF(title, ''), 'Relatório ' || to_char(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI')) AS title
            FROM reports
            WHERE team_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (team_id,),
        )
        if not report:
            return None
        return _jsonable(dict(report))

    return cached_json(f"api:reports:{team_id}:latest", build)


@router.get("/chat/history")
def chat_history(report_id: int | None = None, session: dict = Depends(require_session)):
    uid = str(session.get("clickup_user_id") or "")
    if report_id is not None:
        from app.workspace import current_team_id

        team_id = current_team_id()
        owned = fetch_one(
            "SELECT id FROM reports WHERE id = %s AND team_id = %s",
            (report_id, team_id),
        )
        if not owned:
            return _jsonable({"messages": []})
        rows = fetch_all(
            """
            SELECT author, content, created_at, report_id
            FROM chat_messages
            WHERE clickup_user_id = %s AND report_id = %s
            ORDER BY created_at ASC
            LIMIT 50
            """,
            (uid, report_id),
        )
    else:
        rows = fetch_all(
            """
            SELECT author, content, created_at, report_id
            FROM chat_messages
            WHERE clickup_user_id = %s AND report_id IS NULL
            ORDER BY created_at ASC
            LIMIT 50
            """,
            (uid,),
        )
    messages = [
        {
            "role": "assistant" if r.get("author") == "assistant" else "user",
            "content": r.get("content") or "",
            "report_id": r.get("report_id"),
            "created_at": r.get("created_at"),
        }
        for r in rows
    ]
    return _jsonable({"messages": messages})


@router.post("/extract/refine")
async def extract_refine(session: dict = Depends(require_session)):
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    from app.extract import extract_from_tasks, run_llm_refine

    heuristic = extract_from_tasks()
    refine = await run_llm_refine()
    return _jsonable({"heuristic": heuristic, **refine})


@router.post("/reports/generate")
async def generate(session: dict = Depends(require_session)):
    from app.agent import generate_report
    from app.clickup.cache import cache_clear_all
    from app.workspace import current_team_id, last_sync_fresh

    try:
        team_id = current_team_id()
        uid = str(session.get("clickup_user_id") or "")
        if uid:
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
        sync_stats: dict | None
        if last_sync_fresh(team_id, minutes=10):
            sync_stats = {"skipped": True, "team_id": team_id}
        else:
            sync_stats = run_sync(deep=False, use_cache=True)
        report = await generate_report(session_user_id=uid or None)
        cache_clear_all()
        return _jsonable({"sync": sync_stats, "report": report})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reports/{report_id}")
def get_report(report_id: int, session: dict = Depends(require_session)):
    from app.clickup.cache import cached_json
    from app.workspace import current_team_id

    team_id = current_team_id()

    def build():
        report = fetch_one(
            """
            SELECT *,
                   COALESCE(NULLIF(title, ''), 'Relatório ' || to_char(created_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI')) AS title
            FROM reports
            WHERE id = %s AND team_id = %s
            """,
            (report_id, team_id),
        )
        if not report:
            raise HTTPException(status_code=404, detail="Não encontrado")
        return _jsonable(dict(report))

    return cached_json(f"api:report:{team_id}:{report_id}", build)


@router.post("/sync")
def sync_now(session: dict = Depends(require_session)):
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    from app.clickup.cache import cache_clear_all

    cache_clear_all()
    stats = run_sync(deep=True, use_cache=False)
    extract = extract_from_tasks()
    return {"sync": stats, "extract": extract}


@router.post("/extract")
def extract_now(session: dict = Depends(require_session)):
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    return extract_from_tasks()


@router.get("/leaderboard")
def leaderboard(session: dict = Depends(require_session)):
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    fluxo = fetch_all("SELECT * FROM v_leaderboard_fluxo ORDER BY wip DESC")
    entrega = fetch_all("SELECT * FROM v_leaderboard_entrega ORDER BY cards_concluidos DESC")
    return _jsonable({"fluxo": fluxo, "entrega": entrega})


@router.get("/people")
def people(session: dict = Depends(require_session)):
    rows = fetch_all("SELECT clickup_id, username, display_name, email FROM members ORDER BY display_name")
    if session.get("role") == "admin":
        return _jsonable(rows)
    return _jsonable([r for r in rows if str(r["clickup_id"]) == str(session["clickup_user_id"])])


@router.get("/perfil/{pessoa_id}")
def perfil(pessoa_id: str, session: dict = Depends(require_profile_access)):
    member = fetch_one("SELECT clickup_id, username, display_name, email FROM members WHERE clickup_id = %s", (pessoa_id,))
    profile = fetch_one("SELECT * FROM person_profiles WHERE person_id = %s", (pessoa_id,))
    wip = fetch_one("SELECT * FROM v_wip WHERE person_id = %s", (pessoa_id,))
    aging = fetch_all(
        "SELECT task_id, name, url, status_canonical, days_in_status FROM v_aging WHERE primary_assignee_id = %s",
        (pessoa_id,),
    )
    collab_out = fetch_all(
        """
        SELECT c.*,
               ow.display_name AS owner_name,
               ow.username AS owner_username
        FROM v_collaboration c
        LEFT JOIN members ow ON ow.clickup_id = c.owner_id
        WHERE c.commenter_id = %s
        ORDER BY c.comments DESC
        LIMIT 30
        """,
        (pessoa_id,),
    )
    collab_in = fetch_all(
        """
        SELECT c.*,
               cm.display_name AS commenter_name,
               cm.username AS commenter_username
        FROM v_collaboration c
        LEFT JOIN members cm ON cm.clickup_id = c.commenter_id
        WHERE c.owner_id = %s
        ORDER BY c.comments DESC
        LIMIT 30
        """,
        (pessoa_id,),
    )
    viewing_other = str(session["clickup_user_id"]) != str(pessoa_id)
    return _jsonable(
        {
            "member": member,
            "profile": profile,
            "wip": wip,
            "aging": aging,
            "collaboration_out": collab_out,
            "collaboration_in": collab_in,
            "viewing_as_admin": viewing_other and session.get("role") == "admin",
        }
    )
