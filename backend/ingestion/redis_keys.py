from __future__ import annotations

"""Central Redis key/channel naming + a shared client factory.

A single sync `redis.Redis` client is reused across ingestion, perceive(),
and the /ws/live fanout task. Redis round-trips are sub-millisecond, so a
sync client called from async code (occasionally via asyncio.to_thread for
the heavier agent cycle) is a deliberate simplification for a hackathon
build rather than running a second async Redis client.
"""

import redis

from config import settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def price_key(symbol: str) -> str:
    return f"atlas:market:price:{symbol.lower()}"


def depth_key(symbol: str) -> str:
    return f"atlas:market:depth:{symbol.lower()}"


CHANNEL_TICKS = "atlas:pubsub:ticks"
CHANNEL_REGIME = "atlas:pubsub:regime"
CHANNEL_DECISIONS = "atlas:pubsub:decisions"
