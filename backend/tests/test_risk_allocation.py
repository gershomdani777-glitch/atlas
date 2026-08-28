from agent.nodes import allocate_risk_check
from agent.state import AssetMarketState, Position, ThesisCandidate

BASE_CONFIG = {
    "kelly_fraction": 0.25,
    "max_position_pct": 0.12,
    "max_asset_exposure_pct": 0.20,
    "max_exposure_pct": 0.45,
    "drawdown_stop_pct": 0.08,
    "min_edge_over_cost_bps": 8.0,
}


def _asset(**overrides) -> AssetMarketState:
    defaults = dict(
        symbol="btcusdt",
        price=100.0,
        volatility=0.02,
        depth=500_000,
        liquidity=1.0,
        trend=0.5,
        spread_bps=0.0,
        regime="normal",
        updated_at="2026-01-01T00:00:00+00:00",
        stale=False,
    )
    defaults.update(overrides)
    return AssetMarketState(**defaults)


def _candidate(**overrides) -> ThesisCandidate:
    defaults = dict(
        asset="btcusdt",
        direction="long",
        thesis="test thesis",
        expected_edge_bps=50.0,
        confidence=0.8,
        time_horizon_minutes=30,
        risk_flags=[],
    )
    defaults.update(overrides)
    return ThesisCandidate(**defaults)


def _base_state(asset=None, candidates=None, config=None, positions=None, equity=100_000.0, peak_equity=100_000.0, capital=100_000.0):
    asset = asset or _asset()
    return {
        "cycle": 1,
        "assets": {asset.symbol: asset},
        "capital": capital,
        "equity": equity,
        "peak_equity": peak_equity,
        "throttle": {},
        "config": {**BASE_CONFIG, **(config or {})},
        "candidates": candidates if candidates is not None else [_candidate()],
        "positions": positions or [],
        "memory_context": {},
    }


def test_full_pass_matches_hand_computed_kelly_size():
    state = allocate_risk_check(_base_state())
    decision = state["decisions"][0]
    assert decision.accepted is True
    # cost_bps = 5 + (1/1.0)*2 = 7; edge 50 > 7+8=15 -> passes
    # base_size = 100000*0.25*0.8*(50/10000)/0.02 = 5000
    assert decision.sizing["base_kelly_size"] == 5000.0
    assert decision.size == 5000.0
    assert all(decision.checks.values())


def test_edge_below_cost_rejects_only_that_check():
    state = allocate_risk_check(_base_state(candidates=[_candidate(expected_edge_bps=10.0)]))
    decision = state["decisions"][0]
    assert decision.accepted is False
    assert decision.checks["edge_over_cost"] is False
    other_checks = {k: v for k, v in decision.checks.items() if k != "edge_over_cost"}
    assert all(other_checks.values())


def test_illiquid_asset_rejects_only_liquidity_check():
    state = allocate_risk_check(_base_state(asset=_asset(liquidity=0.1)))
    decision = state["decisions"][0]
    assert decision.accepted is False
    assert decision.checks["liquidity_ok"] is False
    other_checks = {k: v for k, v in decision.checks.items() if k != "liquidity_ok"}
    assert all(other_checks.values())


def test_drawdown_breach_blocks_all_new_positions():
    state = allocate_risk_check(_base_state(equity=90_000.0, peak_equity=100_000.0))
    decision = state["decisions"][0]
    assert decision.accepted is False
    assert decision.checks["drawdown_clear"] is False


def test_zero_asset_capacity_rejects_when_asset_cap_exhausted():
    state = allocate_risk_check(_base_state(config={"max_asset_exposure_pct": 0.0}))
    decision = state["decisions"][0]
    assert decision.accepted is False
    assert decision.checks["asset_capacity"] is False
    assert decision.size == 0.0


def test_portfolio_capacity_breached_when_already_fully_exposed():
    existing_position = Position(
        asset="btcusdt", side="long", size=1000.0, entry_price=100.0, thesis="prior",
        time_horizon_minutes=30, opened_at="2026-01-01T00:00:00+00:00",
    )
    state = allocate_risk_check(_base_state(positions=[existing_position]))  # exposure = 100,000 > 45,000 cap
    decision = state["decisions"][0]
    assert decision.accepted is False
    assert decision.checks["portfolio_capacity"] is False


def test_no_action_direction_is_never_accepted():
    state = allocate_risk_check(_base_state(candidates=[_candidate(direction="no_action")]))
    decision = state["decisions"][0]
    assert decision.accepted is False
    assert decision.checks["direction_present"] is False


def test_stale_asset_rejects_only_not_stale_check():
    state = allocate_risk_check(_base_state(asset=_asset(stale=True)))
    decision = state["decisions"][0]
    assert decision.accepted is False
    assert decision.checks["not_stale"] is False
