from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Callable
from urllib.parse import urlencode

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_TTL = 86400 * 2  # 2 dias; só cai no sync ou ao gerar relatório

_redis = None
_mem: dict[str, tuple[float, Any]] = {}


def _redis_client():
    global _redis
    if _redis is None:
        import redis

        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
    return _redis


def cache_key(token: str, path: str, params: dict | None = None) -> str:
    fp = hashlib.sha256((token or "").encode()).hexdigest()[:12]
    query = urlencode(sorted((params or {}).items()), doseq=True)
    return f"cu:{fp}:{path}?{query}"


def ttl_for(path: str) -> int:
    return CACHE_TTL


def cache_get(key: str) -> Any | None:
    now = time.time()
    mem = _mem.get(key)
    if mem and mem[0] > now:
        return mem[1]
    try:
        raw = _redis_client().get(key)
    except Exception:
        return None
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    _mem[key] = (now + min(CACHE_TTL, 300), value)
    return value


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    ttl = max(15, int(ttl if ttl is not None else CACHE_TTL))
    _mem[key] = (time.time() + ttl, value)
    try:
        _redis_client().setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        logger.debug("Redis cache set falhou para %s", key)


def cache_clear_all() -> None:
    """Apaga todas as chaves cu:* e api:* (ClickUp + respostas da API)."""
    global _mem
    _mem.clear()
    try:
        r = _redis_client()
        batch: list[str] = []
        for pattern in ("cu:*", "api:*"):
            for key in r.scan_iter(match=pattern, count=200):
                batch.append(key)
                if len(batch) >= 200:
                    r.delete(*batch)
                    batch.clear()
        if batch:
            r.delete(*batch)
    except Exception:
        logger.exception("Falha ao limpar cache Redis")


def cached_json(key: str, builder: Callable[[], Any]) -> Any:
    hit = cache_get(key)
    if isinstance(hit, dict) and "v" in hit:
        return hit["v"]
    value = builder()
    cache_set(key, {"v": value})
    return value
