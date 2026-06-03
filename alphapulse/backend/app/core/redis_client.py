"""Singleton async Redis connection pool shared across the app and workers."""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

_pool: redis.ConnectionPool | None = None


def get_redis() -> redis.Redis:
    """Return a Redis client backed by a process-wide connection pool."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            str(settings.REDIS_URL),
            decode_responses=True,
            max_connections=50,
        )
    return redis.Redis(connection_pool=_pool)


async def close_redis() -> None:
    """Disconnect the shared pool during application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
