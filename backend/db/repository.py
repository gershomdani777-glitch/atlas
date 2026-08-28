from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.state import ClosedOutcome, DecisionReceipt, Position, ThrottleUpdate
from db.models import (
    AgentRuntime,
    Asset,
    Decision,
    DecisionReceipt as DecisionReceiptModel,
    EquitySnapshot,
    MemoryEmbedding,
    Order,
    Outcome,
    RiskConfig,
    ThrottleHistory,
    ThrottleStat,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


def get_active_assets(session: Session) -> list[Asset]:
    return list(session.scalars(select(Asset).where(Asset.is_active.is_(True))))


def get_asset_by_symbol(session: Session, symbol: str) -> Asset | None:
    return session.scalar(select(Asset).where(Asset.symbol == symbol.lower()))


# ---------------------------------------------------------------------------
# Risk config
# ---------------------------------------------------------------------------


def get_risk_config(session: Session) -> dict[str, float]:
    rows = session.scalars(select(RiskConfig)).all()
    return {r.config_key: r.config_value for r in rows}


def update_risk_config(session: Session, updates: dict[str, float], updated_by: str = "operator") -> dict[str, float]:
    for key, value in updates.items():
        row = session.scalar(select(RiskConfig).where(RiskConfig.config_key == key))
        if row is None:
            row = RiskConfig(config_key=key, config_value=value, updated_by=updated_by)
            session.add(row)
        else:
            row.config_value = value
            row.updated_by = updated_by
            row.updated_at = utcnow()
    session.flush()
    return get_risk_config(session)


# ---------------------------------------------------------------------------
# Throttle
# ---------------------------------------------------------------------------


def get_throttle_map(session: Session) -> dict[str, dict[str, dict[str, float]]]:
    """asset symbol -> thesis_type -> regime -> multiplier"""
    result: dict[str, dict[str, dict[str, float]]] = {}
    rows = session.scalars(select(ThrottleStat)).all()
    asset_ids = {a.id: a.symbol for a in session.scalars(select(Asset))}
    for row in rows:
        symbol = asset_ids.get(row.asset_id)
        if not symbol:
            continue
        result.setdefault(symbol, {}).setdefault(row.thesis_type, {})[row.regime] = row.throttle_multiplier
    return result


def upsert_throttle_stats(session: Session, asset_id_by_symbol: dict[str, int], cycle: int, updates: list[ThrottleUpdate]) -> None:
    for update in updates:
        asset_id = asset_id_by_symbol.get(update.asset)
        if asset_id is None:
            continue
        row = session.scalar(
            select(ThrottleStat).where(
                ThrottleStat.asset_id == asset_id,
                ThrottleStat.thesis_type == update.thesis_type,
                ThrottleStat.regime == update.regime,
            )
        )
        if row is None:
            row = ThrottleStat(
                asset_id=asset_id,
                thesis_type=update.thesis_type,
                regime=update.regime,
                win_rate=update.win_rate,
                avg_edge_bps=update.avg_edge_bps,
                sample_count=update.sample_count,
                throttle_multiplier=update.multiplier,
            )
            session.add(row)
        else:
            total = row.sample_count + update.sample_count
            row.win_rate = (row.win_rate * row.sample_count + update.win_rate * update.sample_count) / max(total, 1)
            row.avg_edge_bps = (row.avg_edge_bps * row.sample_count + update.avg_edge_bps * update.sample_count) / max(total, 1)
            row.sample_count = total
            row.throttle_multiplier = update.multiplier
            row.updated_at = utcnow()

        session.add(
            ThrottleHistory(
                asset_id=asset_id,
                thesis_type=update.thesis_type,
                regime=update.regime,
                multiplier=update.multiplier,
                cycle=cycle,
            )
        )


# ---------------------------------------------------------------------------
# Decisions / receipts / orders / outcomes
# ---------------------------------------------------------------------------


def record_decision(session: Session, asset_id: int, decision: DecisionReceipt) -> Decision:
    row = Decision(
        cycle=decision.cycle,
        asset_id=asset_id,
        direction=decision.direction,
        thesis=decision.thesis,
        expected_edge_bps=decision.expected_edge_bps,
        confidence=decision.confidence,
        regime=decision.regime,
        accepted=decision.accepted,
        size=decision.size,
        reason=decision.reason,
    )
    session.add(row)
    session.flush()  # obtain row.id

    session.add(
        DecisionReceiptModel(
            decision_id=row.id,
            inputs_snapshot=decision.inputs_snapshot,
            checks=decision.checks,
            sizing=decision.sizing,
            memory_context={"matches": decision.memory_context},
        )
    )
    return row


def record_order_and_outcome(session: Session, asset_id: int, decision_row: Decision, position: Position) -> tuple[Order, Outcome]:
    order = Order(
        decision_id=decision_row.id,
        asset_id=asset_id,
        side=position.side,
        requested_size=decision_row.size,
        filled_size=position.size,
        fill_price=position.entry_price,
        slippage_bps=0.0,
        status="filled",
    )
    session.add(order)
    session.flush()

    outcome = Outcome(
        decision_id=decision_row.id,
        order_id=order.id,
        asset_id=asset_id,
        side=position.side,
        entry_price=position.entry_price,
        size=position.size,
        time_horizon_minutes=position.time_horizon_minutes,
        status="open",
    )
    session.add(outcome)
    session.flush()
    return order, outcome


def get_open_outcomes(session: Session) -> list[Outcome]:
    return list(session.scalars(select(Outcome).where(Outcome.status == "open")))


def close_outcome(session: Session, outcome_id: int, closed: ClosedOutcome) -> None:
    outcome = session.get(Outcome, outcome_id)
    if outcome is None or outcome.status == "closed":
        return
    outcome.closed_at = utcnow()
    outcome.close_reason = closed.close_reason
    outcome.exit_price = closed.exit_price
    outcome.realized_pnl = closed.realized_pnl
    outcome.realized_pnl_bps = closed.realized_pnl_bps
    outcome.direction_correct = closed.direction_correct
    outcome.status = "closed"


def get_decision_receipt(session: Session, decision_id: int) -> dict | None:
    decision = session.get(Decision, decision_id)
    if decision is None:
        return None
    receipt = decision.receipt
    return {
        "decision": {
            "id": decision.id,
            "cycle": decision.cycle,
            "asset": decision.asset.symbol.upper(),
            "direction": decision.direction,
            "thesis": decision.thesis,
            "expected_edge_bps": decision.expected_edge_bps,
            "confidence": decision.confidence,
            "regime": decision.regime,
            "accepted": decision.accepted,
            "size": decision.size,
            "reason": decision.reason,
            "created_at": decision.created_at.isoformat(),
        },
        "inputs_snapshot": receipt.inputs_snapshot if receipt else {},
        "checks": receipt.checks if receipt else {},
        "sizing": receipt.sizing if receipt else {},
        "memory_context": receipt.memory_context if receipt else {},
    }


def list_decisions(session: Session, limit: int = 30, offset: int = 0, accepted: bool | None = None) -> list[Decision]:
    stmt = select(Decision).order_by(Decision.id.desc()).offset(offset).limit(limit)
    if accepted is not None:
        stmt = stmt.where(Decision.accepted == accepted)
    return list(session.scalars(stmt))


# ---------------------------------------------------------------------------
# Memory (pgvector)
# ---------------------------------------------------------------------------


def query_similar_memories(session: Session, asset_id: int, query_embedding: list[float], k: int) -> list[MemoryEmbedding]:
    stmt = (
        select(MemoryEmbedding)
        .where(MemoryEmbedding.asset_id == asset_id)
        .order_by(MemoryEmbedding.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    return list(session.scalars(stmt))


def record_memory_embedding(session: Session, asset_id: int, thesis_text: str, outcome_summary: str, regime: str, embedding: list[float]) -> None:
    session.add(
        MemoryEmbedding(
            asset_id=asset_id,
            thesis_text=thesis_text,
            outcome_summary=outcome_summary,
            regime=regime,
            embedding=embedding,
        )
    )


# ---------------------------------------------------------------------------
# Agent runtime / equity / portfolio
# ---------------------------------------------------------------------------


def get_runtime(session: Session) -> AgentRuntime:
    runtime = session.get(AgentRuntime, 1)
    if runtime is None:
        runtime = AgentRuntime(id=1)
        session.add(runtime)
        session.flush()
    return runtime


def set_running(session: Session, running: bool) -> None:
    runtime = get_runtime(session)
    runtime.is_running = running


def record_equity_snapshot(session: Session, cycle: int, equity: float, capital: float, peak_equity: float) -> None:
    drawdown_pct = (peak_equity - equity) / max(peak_equity, 1e-9)
    session.add(
        EquitySnapshot(cycle=cycle, equity=equity, capital=capital, peak_equity=peak_equity, drawdown_pct=drawdown_pct)
    )


def get_equity_history(session: Session, limit: int = 200) -> list[EquitySnapshot]:
    stmt = select(EquitySnapshot).order_by(EquitySnapshot.cycle.desc()).limit(limit)
    return list(reversed(list(session.scalars(stmt))))


def get_throttle_history(session: Session, limit: int = 500) -> list[ThrottleHistory]:
    stmt = select(ThrottleHistory).order_by(ThrottleHistory.id.desc()).limit(limit)
    return list(reversed(list(session.scalars(stmt))))


def get_market_snapshot(session: Session) -> list[dict]:
    assets = get_active_assets(session)
    return [
        {
            "symbol": a.symbol.upper(),
            "price": a.current_price,
            "volatility": a.current_volatility,
            "liquidity": a.current_liquidity,
            "depth": a.current_depth,
            "trend": a.current_trend,
            "regime": a.current_regime,
            "stale": a.current_stale,
            "updated_at": a.snapshot_updated_at.isoformat() if a.snapshot_updated_at else None,
        }
        for a in assets
    ]


def get_portfolio_open_positions(session: Session) -> list[dict]:
    rows = get_open_outcomes(session)
    assets = {a.id: a.symbol for a in session.scalars(select(Asset))}
    return [
        {
            "id": r.id,
            "asset": assets.get(r.asset_id, "?").upper(),
            "side": r.side,
            "size": r.size,
            "entry_price": r.entry_price,
            "opened_at": r.opened_at.isoformat(),
        }
        for r in rows
    ]


def get_metrics(session: Session) -> dict:
    equity_history = get_equity_history(session)
    throttle_history = get_throttle_history(session)
    assets = {a.id: a.symbol for a in session.scalars(select(Asset))}

    accepted_count = len(list(session.scalars(select(Decision).where(Decision.accepted.is_(True)))))
    rejected_count = len(list(session.scalars(select(Decision).where(Decision.accepted.is_(False)))))

    return {
        "equity_history": [
            {
                "cycle": e.cycle,
                "equity": e.equity,
                "capital": e.capital,
                "peak_equity": e.peak_equity,
                "drawdown_pct": e.drawdown_pct,
                "created_at": e.created_at.isoformat(),
            }
            for e in equity_history
        ],
        "throttle_history": [
            {
                "asset": assets.get(t.asset_id, "?").upper(),
                "thesis_type": t.thesis_type,
                "regime": t.regime,
                "multiplier": t.multiplier,
                "cycle": t.cycle,
            }
            for t in throttle_history
        ],
        "accepted": accepted_count,
        "rejected": rejected_count,
    }
