"""Live Binance public market-data ingestion.

Connects to Binance's combined-stream WebSocket for @ticker (last price)
and @depth20@100ms (top-of-book depth) for the configured asset universe,
and writes last-value-wins snapshots into Redis with an observed_at
timestamp + TTL, so perceive() can distinguish current vs. stale facts.

Binance's @depth20@100ms stream alone fires 10x/second per symbol — the
agent only ever reads this data once per AGENT_CYCLE_SECONDS (default 30s),
so writing to Redis on every single message would burn a free-tier Upstash
command budget for no benefit. Writes are throttled per (symbol, fact type)
to REDIS_WRITE_INTERVAL_SECONDS, comfortably inside STALENESS_TTL_SECONDS
so perceive() never sees stale data because of the throttle itself.

No API key or account needed — this is Binance's public market-data feed.
"""

import asyncio
import json
import logging
import math
import time
from collections import deque
from datetime import datetime, timezone

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings

from .redis_keys import CHANNEL_TICKS, depth_key, get_async_redis_client, price_key

logger = logging.getLogger("atlas.ingestion.binance")

MAX_BACKOFF_SECONDS = 30
PRICE_HISTORY_LENGTH = 120  # rolling samples per symbol (~8-10 min of real ticks), appended on every raw tick

_last_write: dict[str, float] = {}
_price_history: dict[str, deque[float]] = {}


def _record_price(symbol: str, price: float) -> None:
    history = _price_history.setdefault(symbol, deque(maxlen=PRICE_HISTORY_LENGTH))
    history.append(price)


def _realized_volatility(history: deque[float]) -> float:
    """Std-dev of log returns across the window, scaled up so it lands in a
    comparable range to the risk engine's thresholds (a per-4s-tick return
    is tiny; 30 samples ~ a couple minutes is not the horizon those
    thresholds were written for). This is a reasonable proxy for a
    hackathon build, not a calibrated annualized volatility figure."""
    if len(history) < 5:
        return 0.02  # not enough samples yet — same as the old static default
    returns = [math.log(history[i] / history[i - 1]) for i in range(1, len(history)) if history[i - 1] > 0 and history[i] > 0]
    if len(returns) < 4:
        return 0.02
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    stdev = math.sqrt(variance)
    return stdev * math.sqrt(len(history))


def _trend_score(history: deque[float]) -> float:
    """Normalized [0, 1] momentum: 0.5 = flat, >0.7 firmly up, <0.3 firmly
    down. Built from the slope of a simple linear regression over the
    window rather than raw first-vs-last price (less sensitive to a single
    noisy tick at either end)."""
    n = len(history)
    if n < 5:
        return 0.5

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(history) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0 or mean_y == 0:
        return 0.5

    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, history)) / denom
    slope_pct_per_window = (slope * n) / mean_y  # total implied % move across the window
    return 0.5 + 0.5 * math.tanh(slope_pct_per_window * 600)


def _should_write(key: str) -> bool:
    now = time.monotonic()
    if now - _last_write.get(key, 0.0) < settings.redis_write_interval_seconds:
        return False
    _last_write[key] = now
    return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stream_url() -> str:
    streams = []
    for symbol in settings.asset_list:
        streams.append(f"{symbol}@ticker")
        streams.append(f"{symbol}@depth{settings.depth_stream_levels}@100ms")
    return f"{settings.binance_ws_base}/stream?streams=" + "/".join(streams)


async def _handle_ticker(redis_client, payload: dict) -> None:
    symbol = payload["s"].lower()
    price = float(payload["c"])
    # Record every raw tick for accurate stats regardless of the write
    # throttle below — undersampling the history would flatten volatility
    # and trend right back out to noise.
    _record_price(symbol, price)

    if not _should_write(f"price:{symbol}"):
        return

    history = _price_history[symbol]
    fact = {
        "symbol": symbol,
        "price": price,
        "volatility": round(_realized_volatility(history), 6),
        "trend": round(_trend_score(history), 4),
        "observed_at": _now_iso(),
        "ttl_seconds": settings.staleness_ttl_seconds,
    }
    await redis_client.set(price_key(symbol), json.dumps(fact), ex=30)
    await redis_client.publish(CHANNEL_TICKS, json.dumps({"type": "tick", "symbol": symbol.upper(), "price": price}))


async def _handle_depth(redis_client, symbol: str, payload: dict) -> None:
    if not _should_write(f"depth:{symbol}"):
        return
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
    await redis_client.set(depth_key(symbol), json.dumps(fact), ex=30)


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
                    await _handle_ticker(redis_client, data)
                elif "@depth" in stream:
                    await _handle_depth(redis_client, symbol, data)
            except Exception as exc:  # keep the connection alive on a single bad message
                logger.warning("Failed to process Binance message: %s", exc)


async def run_ingestion_loop() -> None:
    """Outer reconnect loop with exponential backoff. Runs forever."""
    redis_client = get_async_redis_client()
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
