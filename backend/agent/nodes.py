import time
import random
from typing import Dict, Any, List
from .state import AgentState, ThesisCandidate, AssetMarketState, DecisionReceipt, Position
from langchain_anthropic import ChatAnthropic
import json

def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def perceive(state: AgentState) -> AgentState:
    # Update market data
    for symbol, asset in state["assets"].items():
        shock = (random.random() - 0.5) * 0.05
        asset.price = round(asset.price * (1 + shock), 4)
        asset.volatility = max(0.005, min(0.1, asset.volatility * 0.9 + abs(shock)))
        asset.trend = max(0.1, min(0.9, asset.trend * 0.9 + (0.1 if shock > 0 else 0)))
        asset.depth = max(10000, asset.depth * (0.95 + random.random() * 0.1))
        asset.liquidity = max(0.1, min(1.5, asset.depth / 500000))
        asset.updated_at = now_iso()
    state["cycle"] += 1
    return state

def interpret(state: AgentState) -> AgentState:
    candidates = []
    # In a real app we'd batch call Claude here. 
    # For now, we mock the LLM output but we'll setup the actual call if API key is provided.
    for symbol, asset in state["assets"].items():
        impulse = (asset.trend - 0.5) * 5 + (random.random() - 0.5)
        if abs(impulse) < 0.5:
            direction = "no_action"
        elif impulse > 0:
            direction = "long"
        else:
            direction = "short"
        
        confidence = max(0.3, min(0.95, 0.5 + abs(impulse) * 0.1 - asset.volatility))
        candidates.append(ThesisCandidate(
            asset=symbol,
            direction=direction,
            thesis="Persistent flow observed" if direction != "no_action" else "Mixed signal",
            expected_edge_bps=10 + confidence * 30,
            confidence=confidence,
            time_horizon_minutes=30,
            risk_flags=["high_volatility"] if asset.volatility > 0.05 else []
        ))
    state["candidates"] = candidates
    return state

def classify_regime(state: AgentState) -> AgentState:
    for symbol, asset in state["assets"].items():
        if asset.volatility > 0.05:
            regime = "high_volatility"
        elif asset.liquidity < 0.5:
            regime = "illiquid"
        elif asset.trend > 0.7:
            regime = "trending"
        elif asset.trend < 0.3:
            regime = "mean_reverting"
        else:
            regime = "normal"
        asset.regime = regime
    return state

def allocate_risk_check(state: AgentState) -> AgentState:
    new_decisions = []
    capital = state["capital"]
    config = state["config"]
    
    current_exposure = sum(p.size * p.entry_price for p in state["positions"])
    
    for candidate in state["candidates"]:
        asset = state["assets"][candidate.asset]
        cost_bps = 5 + (1 / max(0.1, asset.liquidity)) * 2
        
        checks = {
            "direction_present": candidate.direction != "no_action",
            "edge_over_cost": candidate.expected_edge_bps > cost_bps + config.get("min_edge_over_cost_bps", 5),
            "liquidity_ok": asset.liquidity > 0.2,
            "drawdown_clear": (state["peak_equity"] - state["equity"]) / state["peak_equity"] < config.get("drawdown_stop_pct", 0.1),
            "portfolio_capacity": current_exposure < capital * config.get("max_exposure_pct", 0.5)
        }
        
        throttle = state["throttle"].get(asset.symbol, {}).get(asset.regime, 1.0)
        base_size = capital * config.get("kelly_fraction", 0.25) * candidate.confidence * (candidate.expected_edge_bps / 10000) / max(asset.volatility, 0.01)
        requested_size = max(0, min(
            base_size * throttle,
            capital * config.get("max_position_pct", 0.1),
            capital * config.get("max_exposure_pct", 0.5) - current_exposure
        ))
        
        checks["asset_capacity"] = requested_size > 0
        accepted = all(checks.values())
        
        decision = DecisionReceipt(
            id=len(state["decisions"]) + len(new_decisions) + 1,
            cycle=state["cycle"],
            asset=asset.symbol,
            direction=candidate.direction,
            thesis=candidate.thesis,
            expected_edge_bps=candidate.expected_edge_bps,
            confidence=candidate.confidence,
            regime=asset.regime,
            accepted=accepted,
            size=requested_size if accepted else 0.0,
            reason="All deterministic checks passed." if accepted else "Rejected by constraints",
            created_at=now_iso(),
            checks=checks,
            sizing={"base_size": base_size, "throttle": throttle, "final_size": requested_size, "cost_bps": cost_bps}
        )
        new_decisions.append(decision)
        
        if accepted:
            current_exposure += requested_size
            
    state["decisions"] = new_decisions + state["decisions"]
    # keep only last 100
    state["decisions"] = state["decisions"][:100]
    return state

def execute(state: AgentState) -> AgentState:
    accepted_decisions = [d for d in state["decisions"] if d.cycle == state["cycle"] and d.accepted]
    for d in accepted_decisions:
        asset = state["assets"][d.asset]
        fill_price = asset.price * (1 + (1 if d.direction == "long" else -1) * d.sizing["cost_bps"] / 10000)
        pos = Position(
            id=d.id,
            asset=d.asset,
            side=d.direction,
            size=d.size / fill_price,
            entry_price=fill_price,
            opened_at=now_iso()
        )
        state["positions"].append(pos)
    return state

def observe_outcome(state: AgentState) -> AgentState:
    pnl = 0.0
    for pos in state["positions"]:
        current_price = state["assets"][pos.asset].price
        if pos.side == "long":
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size
        else:
            pos.unrealized_pnl = (pos.entry_price - current_price) * pos.size
        pnl += pos.unrealized_pnl
        
    state["equity"] = state["capital"] + pnl
    state["peak_equity"] = max(state["peak_equity"], state["equity"])
    return state

def adapt(state: AgentState) -> AgentState:
    # Update throttles based on recent accepted decisions
    # For MVP, dummy adaptation that slightly favors regimes where positions are profitable
    for pos in state["positions"]:
        if pos.unrealized_pnl > 0:
            asset = state["assets"][pos.asset]
            current_throttle = state["throttle"][pos.asset][asset.regime]
            state["throttle"][pos.asset][asset.regime] = min(1.5, current_throttle * 1.01)
    
    state["history"].append({
        "cycle": state["cycle"],
        "equity": state["equity"],
        "time": now_iso()
    })
    if len(state["history"]) > 100:
        state["history"].pop(0)
    return state
