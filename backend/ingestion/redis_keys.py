from __future__ import annotations

"""Central Redis key/channel naming + a shared client factory.

A single sync `redis.Redis` client is reused across ingestion, perceive(),
and the /ws/live fanout task. Redis round-trips are sub-millisecond, so a
sync client called from async code (occasionally via asyncio.to_thread for
the heavier agent cycle) is a deliberate simplification for a hackathon
build rather than running a second async Redis client.
"""

import redis
import redis.asyncio as aioredis

from config import settings

_client: redis.Redis | None = None
_async_client: aioredis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Sync client — safe only from sync code, or code already off the event
    loop (e.g. via asyncio.to_thread). Never call from a bare `async def`."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def get_async_redis_client() -> aioredis.Redis:
    """Async client — required for any Redis call made directly inside a
    coroutine that shares the main event loop (ingestion, /ws/live), since a
    blocking sync call there stalls every other connection on the server."""
    global _async_client
    if _async_client is None:
        _async_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _async_client


def price_key(symbol: str) -> str:
    return f"atlas:market:price:{symbol.lower()}"


def depth_key(symbol: str) -> str:
    return f"atlas:market:depth:{symbol.lower()}"


CHANNEL_TICKS = "atlas:pubsub:ticks"
CHANNEL_REGIME = "atlas:pubsub:regime"
CHANNEL_DECISIONS = "atlas:pubsub:decisions"
CHANNEL_STATUS = "atlas:pubsub:status"
