"""Rate-limit abstraction (Redis-backed when available, in-memory fallback)."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.exceptions import RateLimitError
from app.services.redis_client import get_redis


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


def parse_rate_limit(spec: str) -> RateLimitRule:
    """Parse strings like '100/minute', '10/second', '1000/hour'."""
    try:
        count_str, period = spec.lower().split("/", maxsplit=1)
        limit = int(count_str)
    except ValueError as exc:
        raise ValueError(f"Invalid rate limit spec: {spec}") from exc

    mapping = {
        "second": 1,
        "sec": 1,
        "s": 1,
        "minute": 60,
        "min": 60,
        "m": 60,
        "hour": 3600,
        "hr": 3600,
        "h": 3600,
        "day": 86400,
        "d": 86400,
    }
    if period not in mapping:
        raise ValueError(f"Unsupported rate limit period: {period}")
    return RateLimitRule(limit=limit, window_seconds=mapping[period])


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def hit(self, key: str, rule: RateLimitRule) -> None:
        now = time.monotonic()
        window_start = now - rule.window_seconds
        bucket = [ts for ts in self._hits[key] if ts >= window_start]
        if len(bucket) >= rule.limit:
            self._hits[key] = bucket
            raise RateLimitError(details={"key": key, "limit": rule.limit})
        bucket.append(now)
        self._hits[key] = bucket


_memory = InMemoryRateLimiter()


class RateLimiter:
    """Abstraction used by middleware / dependencies."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.default_rule = parse_rate_limit(self.settings.rate_limit_default)

    async def check(self, key: str, rule: RateLimitRule | None = None) -> None:
        if not self.settings.rate_limit_enabled:
            return
        active = rule or self.default_rule
        redis_key = f"rl:{key}"
        try:
            client = get_redis()
            count = await client.incr(redis_key)
            if count == 1:
                await client.expire(redis_key, active.window_seconds)
            if count > active.limit:
                raise RateLimitError(details={"key": key, "limit": active.limit})
        except RateLimitError:
            raise
        except Exception:
            await _memory.hit(key, active)
