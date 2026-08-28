from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from agent.runner import run_cycle
from api.routes_config import router as config_router
from api.routes_receipts import router as receipts_router
from api.ws import redis_fanout_task, ws_live_endpoint
from config import settings
from db import repository
from db.session import get_session
from ingestion.binance_ws import run_ingestion_loop
from ingestion.redis_keys import CHANNEL_STATUS, get_redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atlas.main")

_background_tasks: list[asyncio.Task] = []


async def agent_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_cycle)
        except Exception as exc:
            logger.exception("Agent cycle failed: %s", exc)
        await asyncio.sleep(settings.agent_cycle_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _background_tasks.append(asyncio.create_task(run_ingestion_loop()))
    _background_tasks.append(asyncio.create_task(agent_loop()))
    _background_tasks.append(asyncio.create_task(redis_fanout_task()))
    yield
    for task in _background_tasks:
        task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_router)
app.include_router(receipts_router)


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await ws_live_endpoint(websocket)


@app.get("/agent/status")
def get_status():
    with get_session() as session:
        runtime = repository.get_runtime(session)
        return {
            "running": runtime.is_running,
            "cycle": runtime.cycle,
            "cadence_seconds": settings.agent_cycle_seconds,
        }


def _broadcast_status(running: bool) -> None:
    # Already-connected browsers only get a full snapshot once, at connect
    # time — without this, the kill switch would flip the DB but nobody
    # watching would see it change until they reloaded the page.
    try:
        get_redis_client().publish(CHANNEL_STATUS, json.dumps({"type": "status", "running": running}))
    except Exception as exc:
        logger.warning("Failed to publish status change to Redis: %s", exc)


@app.post("/agent/kill")
def kill_agent():
    with get_session() as session:
        repository.set_running(session, False)
    _broadcast_status(False)
    return {"status": "killed"}


@app.post("/agent/resume")
def resume_agent():
    with get_session() as session:
        repository.set_running(session, True)
    _broadcast_status(True)
    return {"status": "resumed"}


@app.get("/agent/decisions")
def get_decisions(limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0), accepted: bool | None = None):
    with get_session() as session:
        rows = repository.list_decisions(session, limit=limit, offset=offset, accepted=accepted)
        symbol_by_id = {a.id: a.symbol for a in repository.get_active_assets(session)}
        return [
            {
                "id": d.id,
                "cycle": d.cycle,
                "asset": symbol_by_id.get(d.asset_id, "").upper(),
                "direction": d.direction,
                "thesis": d.thesis,
                "expected_edge_bps": d.expected_edge_bps,
                "confidence": d.confidence,
                "regime": d.regime,
                "accepted": d.accepted,
                "size": d.size,
                "reason": d.reason,
                "created_at": d.created_at.isoformat(),
            }
            for d in rows
        ]


@app.get("/portfolio")
def get_portfolio():
    with get_session() as session:
        runtime = repository.get_runtime(session)
        positions = repository.get_portfolio_open_positions(session)
        exposure = sum(p["size"] * p["entry_price"] for p in positions)
        return {
            "capital": runtime.capital,
            "equity": runtime.equity,
            "peak_equity": runtime.peak_equity,
            "exposure": exposure,
            "positions": positions,
        }


@app.get("/market")
def get_market():
    with get_session() as session:
        return repository.get_market_snapshot(session)


@app.get("/metrics")
def get_metrics():
    with get_session() as session:
        return repository.get_metrics(session)
