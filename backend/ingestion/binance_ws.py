"""Live Binance public market-data ingestion.

Connects to Binance's combined-stream WebSocket for @ticker (last price)
and @depth20@100ms (top-of-book depth) for the configured asset universe,
and writes last-value-wins snapshots into Redis with an observed_at
timestamp + TTL, so perceive() can distinguish current vs. stale facts.

No API key or account needed — this is Binance's public market-data feed.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings

from .redis_keys import CHANNEL_TICKS, depth_key, get_redis_client, price_key

logger = logging.getLogger("atlas.ingestion.binance")

MAX_BACKOFF_SECONDS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stream_url() -> str:
    streams = []
    for symbol in settings.asset_list:
        streams.append(f"{symbol}@ticker")
        streams.append(f"{symbol}@depth{settings.depth_stream_levels}@100ms")
    return f"{settings.binance_ws_base}/stream?streams=" + "/".join(streams)


def _handle_ticker(redis_client, payload: dict) -> None:
    symbol = payload["s"].lower()
    price = float(payload["c"])
    fact = {
        "symbol": symbol,
        "price": price,
        "observed_at": _now_iso(),
        "ttl_seconds": settings.staleness_ttl_seconds,
    }
    redis_client.set(price_key(symbol), json.dumps(fact), ex=30)
    redis_client.publish(CHANNEL_TICKS, json.dumps({"type": "tick", "symbol": symbol.upper(), "price": price}))


def _handle_depth(redis_client, symbol: str, payload: dict) -> None:
    bids = payload.get("bids", [])
    asks = payload.get("asks", [])
    if not bids or not asks:
        return

    depth_usd = sum(float(p) * float(q) for p, q in bids) + sum(float(p) * float(q) for p, q in asks)
    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid = (best_bid + best_ask) / 2 if (best_bid + best_ask) else 0.0
    spread_bps = ((best_ask - best_bid) / mid) * 10000 if mid else 0.0

    fact = {
        "symbol": symbol,
        "depth_usd": depth_usd,
        "spread_bps": spread_bps,
        "liquidity_score": min(1.5, depth_usd / 500_000),
        "observed_at": _now_iso(),
        "ttl_seconds": settings.staleness_ttl_seconds,
    }
    redis_client.set(depth_key(symbol), json.dumps(fact), ex=30)


async def _consume(redis_client) -> None:
    url = _stream_url()
    logger.info("Connecting to Binance combined stream (%d assets)", len(settings.asset_list))
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        async for raw in ws:
            try:
                message = json.loads(raw)
                stream = message.get("stream", "")
                data = message.get("data", {})
                symbol = stream.split("@")[0]

                if "@ticker" in stream:
                    _handle_ticker(redis_client, data)
                elif "@depth" in stream:
                    _handle_depth(redis_client, symbol, data)
            except Exception as exc:  # keep the connection alive on a single bad message
                logger.warning("Failed to process Binance message: %s", exc)


async def run_ingestion_loop() -> None:
    """Outer reconnect loop with exponential backoff. Runs forever."""
    redis_client = get_redis_client()
    backoff = 1

    while True:
        try:
            await _consume(redis_client)
            backoff = 1  # clean disconnect, reset backoff
        except (ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
            logger.warning("Binance WS disconnected (%s); reconnecting in %ss", exc, backoff)
        except Exception as exc:
            logger.exception("Unexpected ingestion error: %s", exc)

        await asyncio.sleep(backoff)
        backoff = min(MAX_BACKOFF_SECONDS, backoff * 2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_ingestion_loop())
