from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.db import execute, get_pool
from app.status_map import canonical_status, remap_stored_statuses, taxonomy_from_title
from app.clickup.client import ClickUpClient, service_client


def _ms(value: Any) -> datetime | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _field_text(field: dict) -> str | None:
    value = field.get("value")
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("name") or value.get("value") or json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        names = []
        for item in value:
            if isinstance(item, dict):
                names.append(str(item.get("name") or item.get("id") or item))
            else:
                names.append(str(item))
        return ", ".join(names) if names else None
    return str(value)


def upsert_members_from_team(client: ClickUpClient, team_id: str) -> None:
    data = client.teams()
    for team in data.get("teams", []):
        if str(team.get("id")) != str(team_id):
            continue
        for member in team.get("members", []):
            user = member.get("user") or member
            uid = str(user.get("id"))
            role = member.get("role")
            if role is None:
                role = user.get("role")
            execute(
                """
                INSERT INTO members (clickup_id, username, email, display_name, role_raw)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (clickup_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    role_raw = EXCLUDED.role_raw,
                    updated_at = now()
                """,
                (
                    uid,
                    user.get("username"),
                    user.get("email"),
                    user.get("username") or user.get("email"),
                    role,
                ),
            )


def _custom_priority_context(task: dict) -> tuple[str | None, str | None]:
    prio_name = settings.clickup_field_priority.lower()
    ctx_name = settings.clickup_field_context.lower()
    prioridade = None
    contexto = None
    for field in task.get("custom_fields") or []:
        name = (field.get("name") or "").lower()
        text = _field_text(field)
        if name == prio_name:
            prioridade = text
        if name == ctx_name:
            contexto = text
    return prioridade, contexto


def _clickup_user_id(payload: Any) -> str | None:
    """Id de usuário só quando o payload traz um campo de ator. Não inventa."""
    if not isinstance(payload, dict):
        return None
    user = payload.get("user") or payload.get("userid") or payload.get("actor")
    if isinstance(user, dict):
        uid = user.get("id") or user.get("user_id")
        if uid not in (None, "", 0, "0"):
            return str(uid)
    elif user not in (None, "", 0, "0") and not isinstance(user, list):
        return str(user)
    for key in ("user_id", "userid", "userId", "actor_id", "created_by"):
        val = payload.get(key)
        if val not in (None, "", 0, "0") and not isinstance(val, (dict, list)):
            return str(val)
    return None


def _creator_id(task: dict) -> str | None:
    """GET /task sempre traz creator — ator factual da transição first_seen."""
    return _clickup_user_id({"user": task.get("creator")}) or _clickup_user_id(task.get("creator") or {})


def _status_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        label = value.get("status") or value.get("type") or value.get("name")
        return str(label) if label not in (None, "") else None
    text = str(value).strip()
    return text or None


def _norm_status(value: Any) -> str | None:
    label = _status_label(value)
    return label.strip().lower() if label else None


def _is_status_activity(item: dict) -> bool:
    field = str(item.get("field") or item.get("type") or "").strip().lower()
    if field in ("status", "status_changed", "task_status", "1"):
        return True
    after = item.get("after")
    before = item.get("before")
    after_status = isinstance(after, dict) and ("status" in after or "type" in after)
    before_status = isinstance(before, dict) and ("status" in before or "type" in before)
    return after_status or before_status


def _match_activity_actor(
    items: list[dict] | None,
    from_raw: str | None,
    to_raw: str,
) -> str | None:
    """Ator da mudança from→to no histórico GET, se houver. Mais recente ganha."""
    if not items:
        return None
    want_to = _norm_status(to_raw)
    want_from = _norm_status(from_raw)
    matches: list[tuple[int, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        after = _norm_status(item.get("after") or item.get("to") or item.get("status"))
        before = _norm_status(item.get("before") or item.get("from"))
        if not _is_status_activity(item) and after != want_to:
            continue
        if want_to and after and after != want_to:
            continue
        if want_from and before and before != want_from:
            continue
        actor = _clickup_user_id(item)
        if not actor:
            continue
        date_raw = item.get("date") or item.get("date_created") or 0
        try:
            stamp = int(date_raw)
        except (TypeError, ValueError):
            stamp = 0
        matches.append((stamp, actor))
    if not matches:
        return None
    matches.sort(key=lambda row: row[0], reverse=True)
    return matches[0][1]


def _actor_for_transition(
    client: ClickUpClient,
    task_id: str,
    from_raw: str | None,
    to_raw: str,
    *,
    payload: dict | None = None,
    fallback: str | None = None,
) -> str | None:
    actor = _clickup_user_id(payload) if payload else None
    if actor:
        return actor
    actor = _match_activity_actor(client.task_activity(task_id), from_raw, to_raw)
    if actor:
        return actor
    return fallback


def _record_transition(
    conn,
    task_id: str,
    from_raw: str | None,
    to_raw: str,
    at: datetime,
    actor: str | None,
    source: str,
) -> None:
    conn.execute(
        """
        INSERT INTO status_transitions
            (task_id, from_status, to_status, from_canonical, to_canonical, at, actor_clickup_id, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (task_id, at, to_status, source) DO NOTHING
        """,
        (
            task_id,
            from_raw,
            to_raw,
            canonical_status(from_raw) if from_raw else None,
            canonical_status(to_raw),
            at,
            actor,
            source,
        ),
    )


def _seed_history_from_time_in_status(conn, client: ClickUpClient, task_id: str) -> bool:
    data = client.time_in_status(task_id)
    if not data:
        return False
    history = data.get("status_history") or []
    current = data.get("current_status") or {}
    items = list(history)
    if current:
        items.append(current)
    prev_status = None
    wrote = False
    activity = client.task_activity(task_id)
    for item in items:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        total = item.get("total_time") or {}
        since = total.get("since")
        at = None
        if since:
            try:
                at = datetime.fromisoformat(str(since).replace("Z", "+00:00"))
            except ValueError:
                at = None
        if not status or not at:
            continue
        actor = _clickup_user_id(item) or _match_activity_actor(activity, prev_status, status)
        _record_transition(conn, task_id, prev_status, status, at, actor, "time_in_status")
        prev_status = status
        wrote = True
    return wrote


def _collect_task_ids(task: dict) -> set[str]:
    """Ids da task e subtasks aninhadas no payload (paginação não pode omitir filhos)."""
    ids: set[str] = set()
    stack: list[Any] = [task]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            tid = item.get("id")
            if tid not in (None, ""):
                ids.add(str(tid))
            for sub in item.get("subtasks") or []:
                stack.append(sub)
        elif item not in (None, ""):
            ids.add(str(item))
    return ids


def _soft_delete_unseen(conn, seen_ids: set[str], *, list_id: str | None = None) -> None:
    """Marca ausentes do conjunto sincronizado. Não apaga status_transitions/comments."""
    sql = """
        UPDATE tasks
           SET deleted_at = now()
         WHERE deleted_at IS NULL
           AND NOT (clickup_id = ANY(%s::text[]))
    """
    params: list[Any] = [list(seen_ids)]
    if list_id is not None:
        sql += " AND list_id = %s"
        params.append(list_id)
    conn.execute(sql, params)


def _soft_delete_lists_not_synced(conn, synced_list_ids: set[str]) -> None:
    """Listas/spaces que saíram do escopo (arquivados no ClickUp) — tasks somem do espelho vivo."""
    conn.execute(
        """
        UPDATE tasks
           SET deleted_at = now()
         WHERE deleted_at IS NULL
           AND list_id IS NOT NULL
           AND NOT (list_id = ANY(%s::text[]))
        """,
        (list(synced_list_ids),),
    )


def upsert_task(conn, client: ClickUpClient, list_id: str, task: dict, *, detail: bool) -> set[str]:
    task_id = str(task["id"])
    if detail:
        try:
            task = client.task(task_id)
        except Exception:
            pass
    status_obj = task.get("status") or {}
    status_raw = status_obj.get("status") or ""
    status_type = status_obj.get("type") or ""
    if not status_raw:
        status_raw = status_type
    status_canon = canonical_status(status_raw, status_type)
    assignees = [
        {"id": str(a.get("id")), "username": a.get("username")}
        for a in (task.get("assignees") or [])
    ]
    prioridade, contexto = _custom_priority_context(task)
    area, tipo = taxonomy_from_title(task.get("name") or "")
    description = (
        task.get("markdown_description")
        or task.get("text_content")
        or task.get("description")
        or ""
    )
    now = datetime.now(timezone.utc)

    prev = conn.execute(
        "SELECT status_raw, last_status_seen FROM tasks WHERE clickup_id = %s",
        (task_id,),
    ).fetchone()

    conn.execute(
        """
        INSERT INTO tasks (
            clickup_id, custom_id, name, description, url, list_id, parent_id,
            status_raw, status_canonical, date_created, date_updated, date_closed,
            due_date, start_date, archived, assignees, prioridade, contexto, area, tipo,
            last_status_seen, last_status_seen_at, synced_at, deleted_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s::jsonb, %s, %s, %s, %s,
            %s, %s, now(), NULL
        )
        ON CONFLICT (clickup_id) DO UPDATE SET
            custom_id = EXCLUDED.custom_id,
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            url = EXCLUDED.url,
            list_id = EXCLUDED.list_id,
            parent_id = EXCLUDED.parent_id,
            status_raw = EXCLUDED.status_raw,
            status_canonical = EXCLUDED.status_canonical,
            date_created = EXCLUDED.date_created,
            date_updated = EXCLUDED.date_updated,
            date_closed = EXCLUDED.date_closed,
            due_date = EXCLUDED.due_date,
            start_date = EXCLUDED.start_date,
            archived = EXCLUDED.archived,
            assignees = EXCLUDED.assignees,
            prioridade = EXCLUDED.prioridade,
            contexto = EXCLUDED.contexto,
            area = COALESCE(EXCLUDED.area, tasks.area),
            tipo = COALESCE(EXCLUDED.tipo, tasks.tipo),
            last_status_seen = EXCLUDED.last_status_seen,
            last_status_seen_at = CASE
                WHEN tasks.last_status_seen IS DISTINCT FROM EXCLUDED.last_status_seen
                THEN now()
                ELSE COALESCE(tasks.last_status_seen_at, now())
            END,
            synced_at = now(),
            deleted_at = NULL
        """,
        (
            task_id,
            task.get("custom_id"),
            task.get("name") or "",
            description,
            task.get("url"),
            list_id,
            str(task["parent"]) if task.get("parent") else None,
            status_raw,
            status_canon,
            _ms(task.get("date_created")),
            _ms(task.get("date_updated")),
            _ms(task.get("date_closed")),
            _ms(task.get("due_date")),
            _ms(task.get("start_date")),
            bool(task.get("archived")),
            json.dumps(assignees),
            prioridade,
            contexto,
            area,
            tipo,
            status_raw,
            now,
        ),
    )

    if area or tipo:
        conn.execute(
            """
            INSERT INTO task_taxonomy (task_id, area, tipo, source)
            VALUES (%s, %s, %s, 'prefix')
            ON CONFLICT (task_id) DO UPDATE SET
                area = COALESCE(EXCLUDED.area, task_taxonomy.area),
                tipo = COALESCE(EXCLUDED.tipo, task_taxonomy.tipo)
            """,
            (task_id, area, tipo),
        )

    for field in task.get("custom_fields") or []:
        fid = str(field.get("id") or field.get("name"))
        conn.execute(
            """
            INSERT INTO custom_fields (task_id, field_id, field_name, value_text, value_json)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (task_id, field_id) DO UPDATE SET
                field_name = EXCLUDED.field_name,
                value_text = EXCLUDED.value_text,
                value_json = EXCLUDED.value_json
            """,
            (task_id, fid, field.get("name"), _field_text(field), json.dumps(field.get("value"), default=str)),
        )

    for att in task.get("attachments") or []:
        conn.execute(
            """
            INSERT INTO attachments (clickup_id, task_id, title, url, date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (clickup_id) DO UPDATE SET title = EXCLUDED.title, url = EXCLUDED.url
            """,
            (
                str(att.get("id")),
                task_id,
                att.get("title") or att.get("name"),
                att.get("url"),
                _ms(att.get("date")),
            ),
        )

    if prev is None:
        seeded = _seed_history_from_time_in_status(conn, client, task_id)
        if not seeded:
            created = _ms(task.get("date_created")) or now
            actor = _actor_for_transition(
                client, task_id, None, status_raw, fallback=_creator_id(task)
            )
            _record_transition(conn, task_id, None, status_raw, created, actor, "first_seen")
    else:
        old = prev.get("last_status_seen") or prev.get("status_raw")
        if old and status_raw and old != status_raw:
            # poll_diff só ganha ator se GET history/activity (ou o item) trouxer user.
            actor = _actor_for_transition(client, task_id, old, status_raw)
            _record_transition(conn, task_id, old, status_raw, now, actor, "poll_diff")

    creator = _creator_id(task)
    if creator:
        conn.execute(
            """
            UPDATE status_transitions
               SET actor_clickup_id = %s
             WHERE task_id = %s
               AND source = 'first_seen'
               AND actor_clickup_id IS NULL
            """,
            (creator, task_id),
        )
    return _collect_task_ids(task)


def sync_comments(conn, client: ClickUpClient, task_id: str) -> None:
    try:
        comments = client.comments(task_id)
    except Exception:
        return
    for c in comments:
        author = c.get("user") or {}
        text = c.get("comment_text") or c.get("text") or ""
        if not text and isinstance(c.get("comment"), list):
            text = "".join(
                piece.get("text", "") if isinstance(piece, dict) else str(piece)
                for piece in c["comment"]
            )
        conn.execute(
            """
            INSERT INTO comments (clickup_id, task_id, author_id, text, date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (clickup_id) DO UPDATE SET text = EXCLUDED.text, author_id = EXCLUDED.author_id
            """,
            (
                str(c.get("id")),
                task_id,
                str(author["id"]) if author.get("id") else None,
                text,
                _ms(c.get("date")),
            ),
        )


def resolve_primary_assignees() -> None:
    # Hierarquia A6 inalterada: ator das transições > comentários > primeiro assignee.
    execute(
        """
        UPDATE tasks t SET primary_assignee_id = COALESCE(
            (
                SELECT st.actor_clickup_id
                FROM status_transitions st
                WHERE st.task_id = t.clickup_id AND st.actor_clickup_id IS NOT NULL
                GROUP BY st.actor_clickup_id
                ORDER BY count(*) DESC
                LIMIT 1
            ),
            (
                SELECT c.author_id
                FROM comments c
                WHERE c.task_id = t.clickup_id AND c.author_id IS NOT NULL
                GROUP BY c.author_id
                ORDER BY count(*) DESC
                LIMIT 1
            ),
            NULLIF(t.assignees->0->>'id', '')
        )
        """
    )


def run_sync(
    client: ClickUpClient | None = None,
    *,
    deep: bool = True,
    use_cache: bool = True,
) -> dict:
    from app.workspace import persist_team, preferred_team_id

    client = client or service_client()
    client.use_cache = use_cache
    team_id, team_name = client.resolve_team_id(preferred_team_id())
    persist_team(team_id, team_name)

    upsert_members_from_team(client, team_id)
    stats = {"spaces": 0, "lists": 0, "tasks": 0, "team_id": team_id, "team_name": team_name}
    synced_list_ids: set[str] = set()

    with get_pool().connection() as conn:
        for space in client.spaces(team_id):
            sid = str(space["id"])
            conn.execute(
                """
                INSERT INTO spaces (clickup_id, name) VALUES (%s, %s)
                ON CONFLICT (clickup_id) DO UPDATE SET name = EXCLUDED.name, updated_at = now()
                """,
                (sid, space.get("name") or ""),
            )
            stats["spaces"] += 1
            lists: list[tuple[str | None, dict]] = []
            for folder in client.folders(sid):
                fid = str(folder["id"])
                conn.execute(
                    """
                    INSERT INTO folders (clickup_id, space_id, name) VALUES (%s, %s, %s)
                    ON CONFLICT (clickup_id) DO UPDATE SET name = EXCLUDED.name, updated_at = now()
                    """,
                    (fid, sid, folder.get("name") or ""),
                )
                for lst in folder.get("lists") or client.lists_in_folder(fid):
                    lists.append((fid, lst))
            for lst in client.folderless_lists(sid):
                lists.append((None, lst))

            for folder_id, lst in lists:
                lid = str(lst["id"])
                conn.execute(
                    """
                    INSERT INTO lists (clickup_id, space_id, folder_id, name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (clickup_id) DO UPDATE SET
                        space_id = EXCLUDED.space_id,
                        folder_id = EXCLUDED.folder_id,
                        name = EXCLUDED.name,
                        updated_at = now()
                    """,
                    (lid, sid, folder_id, lst.get("name") or ""),
                )
                stats["lists"] += 1
                synced_list_ids.add(lid)
                seen_in_list: set[str] = set()
                page = 0
                while True:
                    payload = client.tasks_in_list(lid, page=page)
                    tasks = payload.get("tasks") or []
                    if not tasks:
                        break
                    for task in tasks:
                        seen_in_list |= _collect_task_ids(task)
                        seen_in_list |= upsert_task(conn, client, lid, task, detail=deep)
                        if deep:
                            sync_comments(conn, client, str(task["id"]))
                        stats["tasks"] += 1
                    if len(tasks) < 100:
                        break
                    page += 1
                _soft_delete_unseen(conn, seen_in_list, list_id=lid)
            conn.commit()
        _soft_delete_lists_not_synced(conn, synced_list_ids)
        conn.commit()

    resolve_primary_assignees()
    remap_stored_statuses()
    execute(
        """
        INSERT INTO sync_state (key, value) VALUES ('last_sync', %s::jsonb)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """,
        (json.dumps({"stats": stats, "at": datetime.now(timezone.utc).isoformat()}),),
    )
    return stats
