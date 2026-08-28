import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
from agent.graph import atlas_app
from agent.state import AssetMarketState

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initial mock state
ASSETS = [
    {"symbol": "BTC-USD", "price": 104820.0, "volatility": 0.010, "depth": 920000.0},
    {"symbol": "ETH-USD", "price": 3825.0, "volatility": 0.014, "depth": 510000.0},
    {"symbol": "SOL-USD", "price": 184.2, "volatility": 0.024, "depth": 180000.0},
]

global_state = {
    "cycle": 0,
    "assets": {
        a["symbol"]: AssetMarketState(
            symbol=a["symbol"],
            price=a["price"],
            volatility=a["volatility"],
            depth=a["depth"],
            liquidity=1.0,
            trend=0.5,
            regime="normal",
            updated_at=""
        ) for a in ASSETS
    },
    "capital": 100000.0,
    "equity": 100000.0,
    "peak_equity": 100000.0,
    "throttle": {
        a["symbol"]: {"normal": 1.0, "trending": 1.0, "mean_reverting": 1.0, "high_volatility": 0.5, "illiquid": 0.2}
        for a in ASSETS
    },
    "config": {
        "max_position_pct": 0.12,
        "max_exposure_pct": 0.45,
        "max_asset_exposure_pct": 0.20,
        "drawdown_stop_pct": 0.08,
        "min_edge_over_cost_bps": 8.0,
        "kelly_fraction": 0.25
    },
    "candidates": [],
    "decisions": [],
    "positions": [],
    "history": []
}

is_running = True

async def agent_loop():
    global global_state
    while True:
        if is_running:
            try:
                # We invoke the graph with the current state.
                # In LangGraph, we can pass the state dict directly.
                global_state = atlas_app.invoke(global_state)
            except Exception as e:
                print(f"Error in agent cycle: {e}")
        await asyncio.sleep(10) # 10 seconds cadence for demo

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(agent_loop())

@app.get("/agent/status")
def get_status():
    return {"running": is_running, "cycle": global_state["cycle"]}

@app.post("/agent/kill")
def kill_agent():
    global is_running
    is_running = False
    return {"status": "killed"}

@app.post("/agent/resume")
def resume_agent():
    global is_running
    is_running = True
    return {"status": "resumed"}

@app.get("/agent/decisions")
def get_decisions(limit: int = 30):
    return [d.dict() for d in global_state["decisions"][:limit]]

@app.get("/portfolio")
def get_portfolio():
    exposure = sum(p.size * p.entry_price for p in global_state["positions"])
    return {
        "capital": global_state["capital"],
        "equity": global_state["equity"],
        "exposure": exposure,
        "positions": [p.dict() for p in global_state["positions"]]
    }

@app.get("/market")
def get_market():
    return {s: a.dict() for s, a in global_state["assets"].items()}

@app.get("/metrics")
def get_metrics():
    return {
        "history": global_state["history"],
        "throttle": global_state["throttle"]
    }
