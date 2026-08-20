from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings
from app.clickup.cache import cache_get, cache_key, cache_set

_http: httpx.Client | None = None


def _http_client() -> httpx.Client:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.Client(timeout=httpx.Timeout(20.0, connect=8.0))
    return _http


class ClickUpError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"ClickUp {status}: {body[:400]}")
        self.status = status
        self.body = body


class ClickUpClient:
    """Cliente somente leitura. Nenhuma rota de escrita."""

    def __init__(self, token: str, bearer: bool = False):
        self.token = token
        self.bearer = bearer
        self._time_in_status_available: bool | None = None
        self._task_activity_available: bool | None = None
        self.use_cache = True

    def _headers(self) -> dict[str, str]:
        auth = f"Bearer {self.token}" if self.bearer else self.token
        return {"Authorization": auth, "Content-Type": "application/json"}

    def get(self, path: str, params: dict | None = None) -> Any:
        url = path if path.startswith("http") else f"https://api.clickup.com/api/v2{path}"
        key = cache_key(self.token, path, params)
        if self.use_cache:
            hit = cache_get(key)
            if hit is not None:
                return hit
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = _http_client().get(url, headers=self._headers(), params=params)
                if resp.status_code == 429:
                    wait = float(resp.headers.get("Retry-After", 1 + attempt))
                    time.sleep(min(wait, 8))
                    continue
                if resp.status_code >= 400:
                    raise ClickUpError(resp.status_code, resp.text)
                data = resp.json()
                if self.use_cache:
                    cache_set(key, data)
                return data
            except ClickUpError as exc:
                if exc.status >= 500:
                    last_exc = exc
                    time.sleep(min(2 ** attempt, 6))
                    continue
                raise
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(min(2 ** attempt, 6))
        if last_exc:
            raise last_exc
        raise RuntimeError("ClickUp request failed")

    def authorized_user(self) -> dict:
        return self.get("/user")

    def teams(self) -> dict:
        return self.get("/team")

    def workspaces(self) -> list[dict]:
        return self.teams().get("teams") or []

    def resolve_team_id(self, configured: str | None = None) -> tuple[str, str]:
        """Devolve (team_id, name). Sem escolha, usa o primeiro workspace do token."""
        configured = (configured or "").strip()
        teams = self.workspaces()
        if not teams:
            raise RuntimeError(
                "Nenhum workspace autorizado para este token. Confira CLICKUP_API_TOKEN."
            )
        if configured:
            for team in teams:
                if str(team.get("id")) == configured:
                    return configured, str(team.get("name") or configured)
        team = teams[0]
        return str(team["id"]), str(team.get("name") or team["id"])

    def spaces(self, team_id: str) -> list[dict]:
        return self.get(f"/team/{team_id}/space", params={"archived": "false"}).get("spaces", [])

    def folders(self, space_id: str) -> list[dict]:
        return self.get(f"/space/{space_id}/folder", params={"archived": "false"}).get("folders", [])

    def folderless_lists(self, space_id: str) -> list[dict]:
        return self.get(f"/space/{space_id}/list", params={"archived": "false"}).get("lists", [])

    def lists_in_folder(self, folder_id: str) -> list[dict]:
        return self.get(f"/folder/{folder_id}/list", params={"archived": "false"}).get("lists", [])

    def tasks_in_list(self, list_id: str, page: int = 0) -> dict:
        return self.get(
            f"/list/{list_id}/task",
            params={
                "archived": "false",
                "include_closed": "true",
                "subtasks": "true",
                "page": page,
            },
        )

    def task(self, task_id: str) -> dict:
        return self.get(f"/task/{task_id}", params={"include_subtasks": "true", "include_markdown_description": "true"})

    def comments(self, task_id: str) -> list[dict]:
        return self.get(f"/task/{task_id}/comment").get("comments", [])

    def time_in_status(self, task_id: str) -> dict | None:
        if self._time_in_status_available is False:
            return None
        try:
            data = self.get(f"/task/{task_id}/time_in_status")
            self._time_in_status_available = True
            return data
        except ClickUpError as exc:
            if exc.status in (400, 401, 403, 404):
                self._time_in_status_available = False
                return None
            raise

    def task_activity(self, task_id: str) -> list[dict] | None:
        """Histórico da task via GET, se a API expor.

        Quem mudou o status não vem em GET /task nem em time_in_status (schema
        só tem status + total_time). Webhooks (history_items.user) estão fora
        deste MVP. POST /team/{team_id}/audit é Enterprise e não é GET — não
        chamamos. Tentamos GET /task/{id}/history e /activity uma vez; 4xx
        desliga a fonte no cliente (mesmo padrão de time_in_status).
        """
        if self._task_activity_available is False:
            return None
        last_denied: ClickUpError | None = None
        for path in (f"/task/{task_id}/history", f"/task/{task_id}/activity"):
            try:
                data = self.get(path)
                self._task_activity_available = True
                return _activity_items(data)
            except ClickUpError as exc:
                if exc.status in (400, 401, 403, 404):
                    last_denied = exc
                    continue
                raise
        if last_denied is not None:
            self._task_activity_available = False
        return None


def _activity_items(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("history", "history_items", "activities", "events", "items"):
        items = data.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return [data] if any(key in data for key in ("user", "field", "after", "before", "history_items")) else []


def service_client() -> ClickUpClient:
    if not settings.clickup_api_token:
        raise RuntimeError("CLICKUP_API_TOKEN ausente")
    return ClickUpClient(settings.clickup_api_token, bearer=False)
