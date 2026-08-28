from __future__ import annotations

"""Owns the seam between the pure LangGraph computation and persistence:
hydrate a fresh AgentState from Postgres/Redis, invoke the 7-node graph,
then persist everything it produced. This replaces the old in-memory
global_state dict entirely — every cycle starts from durable state and
ends by durably recording it, so a Render cold start loses nothing."""

import json
import logging
from datetime import datetime, timezone

from config import settings
from db import repository
from db.models import Decision
from db.session import get_session
from ingestion.redis_keys import CHANNEL_DECISIONS, CHANNEL_REGIME, get_redis_client

from . import memory
from .graph import atlas_app
from .state import AgentState, AssetMarketState, Position

logger = logging.getLogger("atlas.runner")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hydrate_state(session) -> AgentState | None:
    runtime = repository.get_runtime(session)
    if not runtime.is_running:
        return None

    assets_rows = repository.get_active_assets(session)
    if not assets_rows:
        logger.warning("No active assets configured; run db/init_db.py first.")
        return None

    assets: dict[str, AssetMarketState] = {}
    for asset in assets_rows:
        assets[asset.symbol] = AssetMarketState(
            symbol=asset.symbol,
            price=0.0,
            volatility=0.02,
            depth=0.0,
            liquidity=0.0,
            trend=0.5,
            regime="normal",
            updated_at=_now_iso(),
            stale=True,
        )

    config = repository.get_risk_config(session)
    config["staleness_ttl_seconds"] = settings.staleness_ttl_seconds

    positions: list[Position] = []
    for outcome in repository.get_open_outcomes(session):
        asset = next((a for a in assets_rows if a.id == outcome.asset_id), None)
        if asset is None:
            continue
        decision = session.get(Decision, outcome.decision_id)
        positions.append(
            Position(
                id=outcome.order_id,
                outcome_id=outcome.id,
                decision_id=outcome.decision_id,
                asset=asset.symbol,
                side=outcome.side,
                size=outcome.size,
                entry_price=outcome.entry_price,
                thesis=decision.thesis if decision else "",
                time_horizon_minutes=outcome.time_horizon_minutes,
                opened_at=outcome.opened_at.isoformat(),
            )
        )

    return AgentState(
        cycle=runtime.cycle + 1,
        assets=assets,
        capital=runtime.capital,
        equity=runtime.equity,
        peak_equity=runtime.peak_equity,
        throttle=repository.get_throttle_map(session),
        config=config,
        candidates=[],
        llm_degraded=False,
        memory_context={},
        decisions=[],
        positions=positions,
        closed_outcomes=[],
        regime_changes=[],
        throttle_updates=[],
        pending_memory_writes=[],
    )


def persist_state(session, state: AgentState) -> tuple[list[dict], list[dict]]:
    """Returns (decision_events, regime_events) for post-commit WS fanout."""
    asset_rows = repository.get_active_assets(session)
    asset_id_by_symbol = {a.symbol: a.id for a in asset_rows}

    for asset_row in asset_rows:
        live = state["assets"].get(asset_row.symbol)
        if live is None:
            continue
        asset_row.current_price = live.price
        asset_row.current_volatility = live.volatility
        asset_row.current_liquidity = live.liquidity
        asset_row.current_depth = live.depth
        asset_row.current_trend = live.trend
        asset_row.current_regime = live.regime
        asset_row.current_stale = live.stale

    decision_rows = []
    for decision in state["decisions"]:
        asset_id = asset_id_by_symbol.get(decision.asset)
        if asset_id is None:
            continue
        decision_rows.append(repository.record_decision(session, asset_id, decision))

    actionable_indices = [
        i for i, d in enumerate(state["decisions"]) if d.accepted and d.direction != "no_action"
    ]
    new_positions = [p for p in state["positions"] if p.id == 0]
    for idx, position in zip(actionable_indices, new_positions):
        decision = state["decisions"][idx]
        asset_id = asset_id_by_symbol.get(decision.asset)
        if asset_id is None:
            continue
        repository.record_order_and_outcome(session, asset_id, decision_rows[idx], position)

    for closed in state["closed_outcomes"]:
        if closed.outcome_id:
            repository.close_outcome(session, closed.outcome_id, closed)

    repository.upsert_throttle_stats(session, asset_id_by_symbol, state["cycle"], state["throttle_updates"])
    repository.record_equity_snapshot(session, state["cycle"], state["equity"], state["capital"], state["peak_equity"])

    runtime = repository.get_runtime(session)
    runtime.cycle = state["cycle"]
    runtime.capital = state["capital"]
    runtime.equity = state["equity"]
    runtime.peak_equity = state["peak_equity"]

    symbol_by_asset_id = {i: s for s, i in asset_id_by_symbol.items()}
    decision_events = [
        {
            # Must match the /agent/decisions REST shape exactly — the
            # frontend renders WS-delivered and REST-fetched decisions
            # through the same component with no distinction, so a partial
            # payload here crashes the UI the instant a live decision arrives.
            "id": row.id,
            "cycle": row.cycle,
            "asset": symbol_by_asset_id.get(row.asset_id, "").upper(),
            "direction": row.direction,
            "thesis": row.thesis,
            "expected_edge_bps": row.expected_edge_bps,
            "confidence": row.confidence,
            "accepted": row.accepted,
            "size": row.size,
            "reason": row.reason,
            "regime": row.regime,
            "created_at": row.created_at.isoformat() if row.created_at else _now_iso(),
        }
        for row in decision_rows
    ]
    regime_events = [rc.model_dump() for rc in state["regime_changes"]]
    return decision_events, regime_events


def run_cycle() -> None:
    # Hydrate and persist each get their own short-lived session — the graph
    # invocation in between (which can block for seconds on a slow/retrying
    # Gemini call) must never hold a DB connection open. Against Supabase's
    # transaction-mode pooler in particular, an idle-but-checked-out
    # connection during unrelated network I/O starves other requests trying
    # to acquire a connection from the same pool.
    with get_session() as session:
        state = hydrate_state(session)
    if state is None:
        return

    result_state = atlas_app.invoke(state)

    with get_session() as session:
        decision_events, regime_events = persist_state(session, result_state)

    # Best-effort side effects, only after the transaction above committed cleanly.
    for record in result_state["pending_memory_writes"]:
        memory.embed_and_store(record)

    try:
        redis_client = get_redis_client()
        for event in decision_events:
            redis_client.publish(CHANNEL_DECISIONS, json.dumps({"type": "decision", "decision": event}))
        for event in regime_events:
            redis_client.publish(CHANNEL_REGIME, json.dumps({"type": "regime", **event}))
    except Exception as exc:
        logger.warning("Failed to publish cycle events to Redis: %s", exc)
