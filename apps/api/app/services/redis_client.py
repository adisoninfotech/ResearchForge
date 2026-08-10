"""Redis connectivity helpers."""

from __future__ import annotations

from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis[Any] | None = None


def get_redis() -> Redis[Any]:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def check_redis() -> bool:
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception:
        return False


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
