"""FastAPI WebSocket endpoint. A single backend-side Redis subscription is
fanned out in-process to every connected browser, rather than each browser
opening its own Upstash pub/sub connection (real concern on a free-tier
connection cap)."""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from config import settings
from db.session import get_session
from db import repository
from ingestion.redis_keys import CHANNEL_DECISIONS, CHANNEL_REGIME, CHANNEL_STATUS, CHANNEL_TICKS

logger = logging.getLogger("atlas.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    def register(self, websocket: WebSocket) -> None:
        self.active.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        dead = []
        payload = json.dumps(message)
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def build_snapshot_payload() -> dict:
    def _read() -> dict:
        with get_session() as session:
            runtime = repository.get_runtime(session)
            positions = repository.get_portfolio_open_positions(session)
            decisions = repository.list_decisions(session, limit=10)
            symbol_by_id = {a.id: a.symbol for a in repository.get_active_assets(session)}
            return {
                "type": "snapshot",
                "running": runtime.is_running,
                "cycle": runtime.cycle,
                "capital": runtime.capital,
                "equity": runtime.equity,
                "peak_equity": runtime.peak_equity,
                "positions": positions,
                "recent_decisions": [
                    # Must match the /agent/decisions REST shape exactly —
                    # this feeds the same DecisionRow component as the REST
                    # fetch, with no distinction made between the two.
                    {
                        "id": d.id,
                        "cycle": d.cycle,
                        "asset": symbol_by_id.get(d.asset_id, "").upper(),
                        "direction": d.direction,
                        "thesis": d.thesis,
                        "expected_edge_bps": d.expected_edge_bps,
                        "confidence": d.confidence,
                        "accepted": d.accepted,
                        "size": d.size,
                        "reason": d.reason,
                        "regime": d.regime,
                        "created_at": d.created_at.isoformat(),
                    }
                    for d in decisions
                ],
            }

    return await asyncio.to_thread(_read)


async def redis_fanout_task() -> None:
    """Runs forever as a background task; reconnects on any pubsub error."""
    while True:
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.subscribe(CHANNEL_TICKS, CHANNEL_REGIME, CHANNEL_DECISIONS, CHANNEL_STATUS)
            logger.info("Subscribed to Redis pubsub channels for /ws/live fanout")
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    await manager.broadcast(json.loads(message["data"]))
                except Exception as exc:
                    logger.warning("Failed to broadcast pubsub message: %s", exc)
        except Exception as exc:
            logger.warning("Redis fanout task error: %s; retrying in 5s", exc)
            await asyncio.sleep(5)


async def ws_live_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    # Fetch + send the snapshot BEFORE registering for broadcast — otherwise a
    # live tick can be fanned out to this socket while the snapshot's DB read
    # is still in flight, so the client's first frame isn't guaranteed to be
    # the snapshot it needs to render non-empty state.
    snapshot = await build_snapshot_payload()
    await websocket.send_text(json.dumps(snapshot))
    manager.register(websocket)
    try:
        while True:
            # Clients don't need to send anything; this just detects disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
