"""Redis caching layer for expensive / rate-limited external API calls.

Two entry points:

* ``cached_json`` — a low-level read-through helper.
* ``@redis_cache`` — a decorator that wraps any async function returning a
  JSON-serialisable value, applying a stampede-protected read-through cache.

The decorator implements a lightweight lock so that, on a cache miss, only one
coroutine recomputes the value while others briefly wait — critical when an
upstream provider (FMP / Polygon) enforces tight rate limits.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from app.core.redis_client import get_redis

P = ParamSpec("P")
T = TypeVar("T")

_LOCK_TTL_MS = 5_000
_LOCK_WAIT_SECONDS = 0.05
_LOCK_MAX_RETRIES = 60


def _make_key(namespace: str, *parts: Any) -> str:
    raw = ":".join(str(p) for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"cache:{namespace}:{digest}"


async def cached_json(
    namespace: str,
    key_parts: tuple[Any, ...],
    ttl: int,
    producer: Callable[[], Awaitable[Any]],
) -> Any:
    """Read-through cache for a single JSON value with stampede protection."""
    redis = get_redis()
    key = _make_key(namespace, *key_parts)

    hit = await redis.get(key)
    if hit is not None:
        return json.loads(hit)

    lock_key = f"{key}:lock"
    have_lock = await redis.set(lock_key, "1", nx=True, px=_LOCK_TTL_MS)

    if not have_lock:
        # Another worker is producing the value; poll briefly for the result.
        for _ in range(_LOCK_MAX_RETRIES):
            await asyncio.sleep(_LOCK_WAIT_SECONDS)
            hit = await redis.get(key)
            if hit is not None:
                return json.loads(hit)
        # Fall through and compute it ourselves if the lock holder stalled.

    try:
        value = await producer()
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
        return value
    finally:
        await redis.delete(lock_key)


def redis_cache(namespace: str, ttl: int) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator applying :func:`cached_json` to an async function.

    The cache key is derived from the function's positional and keyword
    arguments, so ``await fetch_quote("AAPL")`` and ``await fetch_quote("MSFT")``
    are cached independently.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            key_parts = (func.__qualname__, *args, *sorted(kwargs.items()))
            return await cached_json(  # type: ignore[return-value]
                namespace,
                key_parts,
                ttl,
                lambda: func(*args, **kwargs),
            )

        return wrapper

    return decorator


async def invalidate(namespace: str, *parts: Any) -> None:
    """Delete a specific cache entry (e.g. after a contributor edits data)."""
    await get_redis().delete(_make_key(namespace, *parts))
