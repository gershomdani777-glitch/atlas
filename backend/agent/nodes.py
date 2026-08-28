import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from ingestion.redis_keys import depth_key, get_redis_client, price_key

from .llm import get_thesis_candidates
from .state import (
    AgentState,
    ClosedOutcome,
    DecisionReceipt,
    Position,
    RegimeChange,
    ThrottleUpdate,
)

logger = logging.getLogger("atlas.nodes")

# PRD 5.2 order: constraints are checked and the *first* failure in this
# order is surfaced as the human-readable rejection reason, even though all
# checks are computed (the accept/reject outcome is unaffected by ordering).
CHECK_ORDER = [
    "direction_present",
    "not_stale",
    "edge_over_cost",
    "liquidity_ok",
    "drawdown_clear",
    "portfolio_capacity",
    "asset_capacity",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def get_throttle(state: AgentState, asset: str, direction: str, regime: str) -> float:
    return state["throttle"].get(asset, {}).get(direction, {}).get(regime, 1.0)


# ---------------------------------------------------------------------------
# Stage 1: Perceive
# ---------------------------------------------------------------------------


def perceive(state: AgentState) -> AgentState:
    ttl_default = state["config"].get("staleness_ttl_seconds", 5)
    now = datetime.now(timezone.utc)

    try:
        redis_client = get_redis_client()
        redis_client.ping()
    except Exception as exc:
        # Redis itself is unreachable: degrade to all-stale rather than
        # crashing the cycle, mirroring the LLM's own failure handling.
        logger.warning("perceive(): Redis unavailable (%s); marking all assets stale this cycle.", exc)
        for asset in state["assets"].values():
            asset.stale = True
        return state

    for symbol, asset in state["assets"].items():
        price_fact = redis_client.get(price_key(symbol))
        depth_fact = redis_client.get(depth_key(symbol))

        import json

        fresh_price = None
        fresh_depth = None
        for raw, target in ((price_fact, "price"), (depth_fact, "depth")):
            if not raw:
                continue
            try:
                fact = json.loads(raw)
                observed_at = _parse_iso(fact["observed_at"])
                ttl = fact.get("ttl_seconds", ttl_default)
                if (now - observed_at).total_seconds() <= ttl:
                    if target == "price":
                        fresh_price = fact
                    else:
                        fresh_depth = fact
            except (ValueError, KeyError, TypeError):
                continue

        if fresh_price is None and fresh_depth is None:
            # Nothing fresh in Redis for this asset this cycle: keep the
            # last-known values but mark stale so downstream stages treat
            # it as untradeable rather than silently reusing old prices.
            asset.stale = True
            continue

        asset.stale = False
        if fresh_price:
            asset.price = fresh_price["price"]
        if fresh_depth:
            asset.depth = fresh_depth["depth_usd"]
            asset.liquidity = fresh_depth["liquidity_score"]
            asset.spread_bps = fresh_depth.get("spread_bps", asset.spread_bps)
        asset.updated_at = now_iso()

    return state


# ---------------------------------------------------------------------------
# Stage 2: Interpret (Claude/Gemini reasoning layer — propose only)
# ---------------------------------------------------------------------------


def interpret(state: AgentState) -> AgentState:
    try:
        candidates, degraded = get_thesis_candidates(state)
        state["candidates"] = candidates
        state["llm_degraded"] = degraded
    except Exception as exc:  # pragma: no cover - defensive, get_thesis_candidates already catches
        logger.warning("interpret() failed unexpectedly: %s", exc)
        state["candidates"] = []
        state["llm_degraded"] = True
    return state


# ---------------------------------------------------------------------------
# Stage 3: Classify Regime (deterministic)
# ---------------------------------------------------------------------------


def classify_regime(state: AgentState) -> AgentState:
    changes = []
    for symbol, asset in state["assets"].items():
        previous = asset.regime
        if asset.stale:
            regime = "illiquid"
        elif asset.volatility > 0.05:
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
        if regime != previous:
            changes.append(RegimeChange(asset=symbol, previous_regime=previous, new_regime=regime, cycle=state["cycle"]))
    state["regime_changes"] = changes
    return state


# ---------------------------------------------------------------------------
# Stage 4: Allocate & Risk-Check (deterministic control layer)
# ---------------------------------------------------------------------------


def allocate_risk_check(state: AgentState) -> AgentState:
    config = state["config"]
    capital = state["capital"]
    current_exposure = sum(p.size * p.entry_price for p in state["positions"])

    # PRD 5.2 step 5: rank survivors by risk-adjusted edge per unit of
    # capital before allocating, rather than accepting in arbitrary order.
    ranked = sorted(state["candidates"], key=lambda c: c.expected_edge_bps * c.confidence, reverse=True)

    drawdown_pct = (state["peak_equity"] - state["equity"]) / max(state["peak_equity"], 1e-9)
    drawdown_breached = drawdown_pct >= config.get("drawdown_stop_pct", 0.08)

    new_decisions = []
    for candidate in ranked:
        asset = state["assets"][candidate.asset]
        cost_bps = 5 + (1 / max(asset.liquidity, 0.05)) * 2 + asset.spread_bps

        checks = {
            "direction_present": candidate.direction != "no_action",
            "not_stale": not asset.stale,
            "edge_over_cost": candidate.expected_edge_bps > cost_bps + config.get("min_edge_over_cost_bps", 8.0),
            "liquidity_ok": asset.liquidity > 0.2,
            "drawdown_clear": not drawdown_breached,
        }

        throttle = get_throttle(state, asset.symbol, candidate.direction, asset.regime)
        base_size = (
            capital
            * config.get("kelly_fraction", 0.25)
            * candidate.confidence
            * (candidate.expected_edge_bps / 10000)
            / max(asset.volatility, 0.01)
        )
        throttled_size = max(0.0, base_size * throttle)

        max_position = capital * config.get("max_position_pct", 0.12)
        max_asset_exposure = capital * config.get("max_asset_exposure_pct", 0.20)
        max_total_exposure = capital * config.get("max_exposure_pct", 0.45)

        asset_exposure = sum(p.size * p.entry_price for p in state["positions"] if p.asset == asset.symbol)

        requested_size = min(
            throttled_size,
            max_position,
            max(0.0, max_asset_exposure - asset_exposure),
            max(0.0, max_total_exposure - current_exposure),
        )
        requested_size = max(0.0, requested_size)

        # max_position_pct/max_asset_exposure_pct are resize caps already applied
        # above (requested_size is pre-clamped to them), not accept/reject gates —
        # a candidate that gets resized to 0 by them is caught by asset_capacity below.
        checks["portfolio_capacity"] = current_exposure < max_total_exposure
        checks["asset_capacity"] = requested_size > 0

        accepted = all(checks.values())
        reason = "All deterministic checks passed."
        if not accepted:
            failing = next((name for name in CHECK_ORDER if not checks.get(name, True)), None)
            reason = f"Rejected: {failing.replace('_', ' ')}" if failing else "Rejected by constraints"

        decision = DecisionReceipt(
            cycle=state["cycle"],
            asset=asset.symbol,
            direction=candidate.direction,
            thesis=candidate.thesis,
            expected_edge_bps=candidate.expected_edge_bps,
            confidence=candidate.confidence,
            regime=asset.regime,
            accepted=accepted,
            size=requested_size if accepted else 0.0,
            reason=reason,
            time_horizon_minutes=candidate.time_horizon_minutes,
            created_at=now_iso(),
            checks=checks,
            sizing={
                "base_kelly_size": round(base_size, 2),
                "throttle_multiplier": throttle,
                "throttled_size": round(throttled_size, 2),
                "max_position_cap": round(max_position, 2),
                "max_asset_exposure_cap": round(max_asset_exposure, 2),
                "max_total_exposure_cap": round(max_total_exposure, 2),
                "final_size": round(requested_size, 2),
                "estimated_cost_bps": round(cost_bps, 2),
            },
            inputs_snapshot={
                "price": asset.price,
                "volatility": asset.volatility,
                "liquidity": asset.liquidity,
                "depth": asset.depth,
                "spread_bps": asset.spread_bps,
                "regime": asset.regime,
                "stale": asset.stale,
                "observed_at": asset.updated_at,
                "drawdown_pct": round(drawdown_pct, 4),
            },
            memory_context=state["memory_context"].get(asset.symbol, []),
        )
        new_decisions.append(decision)

        if accepted and candidate.direction != "no_action":
            current_exposure += requested_size

    state["decisions"] = new_decisions
    return state


# ---------------------------------------------------------------------------
# Stage 5: Execute (simulated fills)
# ---------------------------------------------------------------------------


def execute(state: AgentState) -> AgentState:
    for decision in state["decisions"]:
        if not decision.accepted or decision.direction == "no_action":
            continue
        asset = state["assets"][decision.asset]
        slippage_bps = decision.sizing["estimated_cost_bps"]
        direction_sign = 1 if decision.direction == "long" else -1
        fill_price = asset.price * (1 + direction_sign * slippage_bps / 10000)
        filled_size = decision.size / fill_price if fill_price > 0 else 0.0

        decision.fill = {
            "fill_price": round(fill_price, 6),
            "filled_size": round(filled_size, 8),
            "slippage_bps": slippage_bps,
        }

        state["positions"].append(
            Position(
                asset=decision.asset,
                side=decision.direction,
                size=filled_size,
                entry_price=fill_price,
                thesis=decision.thesis,
                time_horizon_minutes=decision.time_horizon_minutes,
                opened_at=now_iso(),
            )
        )
    return state


# ---------------------------------------------------------------------------
# Stage 6: Observe Outcome (mark-to-market, close expired positions)
# ---------------------------------------------------------------------------


def observe_outcome(state: AgentState) -> AgentState:
    now = datetime.now(timezone.utc)
    still_open = []
    closed = []
    realized_total = 0.0

    for position in state["positions"]:
        asset = state["assets"].get(position.asset)
        current_price = asset.price if asset else position.entry_price
        direction_sign = 1 if position.side == "long" else -1
        position.unrealized_pnl = (current_price - position.entry_price) * position.size * direction_sign

        opened_at = _parse_iso(position.opened_at)
        elapsed_minutes = (now - opened_at).total_seconds() / 60.0

        if elapsed_minutes >= position.time_horizon_minutes:
            realized_pnl = position.unrealized_pnl
            realized_pnl_bps = (realized_pnl / max(position.entry_price * position.size, 1e-9)) * 10000
            realized_total += realized_pnl
            closed.append(
                ClosedOutcome(
                    outcome_id=position.outcome_id,
                    decision_id=position.decision_id,
                    asset=position.asset,
                    side=position.side,
                    entry_price=position.entry_price,
                    exit_price=current_price,
                    size=position.size,
                    thesis=position.thesis,
                    regime=asset.regime if asset else "normal",
                    realized_pnl=realized_pnl,
                    realized_pnl_bps=realized_pnl_bps,
                    direction_correct=realized_pnl > 0,
                    closed_at=now_iso(),
                    close_reason="time_horizon_elapsed",
                )
            )
        else:
            still_open.append(position)

    state["positions"] = still_open
    state["closed_outcomes"] = closed
    state["capital"] = state["capital"] + realized_total
    unrealized_total = sum(p.unrealized_pnl for p in still_open)
    state["equity"] = state["capital"] + unrealized_total
    state["peak_equity"] = max(state["peak_equity"], state["equity"])
    return state


# ---------------------------------------------------------------------------
# Stage 7: Adapt (throttle + outcome-conditioned memory)
# ---------------------------------------------------------------------------


def adapt(state: AgentState) -> AgentState:
    throttle_updates = []
    memory_writes = []

    for outcome in state["closed_outcomes"]:
        current = get_throttle(state, outcome.asset, outcome.side, outcome.regime)
        step = 0.05 if outcome.realized_pnl > 0 else -0.05
        new_multiplier = min(1.5, max(0.2, current * 0.98 + step))

        state["throttle"].setdefault(outcome.asset, {}).setdefault(outcome.side, {})[outcome.regime] = new_multiplier

        throttle_updates.append(
            ThrottleUpdate(
                asset=outcome.asset,
                thesis_type=outcome.side,
                regime=outcome.regime,
                win_rate=1.0 if outcome.direction_correct else 0.0,
                avg_edge_bps=outcome.realized_pnl_bps,
                sample_count=1,
                multiplier=new_multiplier,
            )
        )

        outcome_summary = (
            f"{'Profitable' if outcome.realized_pnl > 0 else 'Losing'} {outcome.side} on {outcome.asset}: "
            f"{outcome.realized_pnl_bps:.1f} bps realized in {outcome.regime} regime."
        )
        memory_writes.append(
            {
                "asset": outcome.asset,
                "thesis_text": outcome.thesis,
                "outcome_summary": outcome_summary,
                "regime": outcome.regime,
            }
        )

    state["throttle_updates"] = throttle_updates
    state["pending_memory_writes"] = memory_writes
    return state
