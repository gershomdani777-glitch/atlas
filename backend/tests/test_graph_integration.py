"""End-to-end test of the 7-node LangGraph loop against an in-memory
SQLite DB. Gemini is monkeypatched (no network/API key needed). The
memory_embeddings table is excluded — it uses a pgvector column type that
SQLite can't create; pgvector-specific behavior is covered separately by
unit tests on agent/memory.py instead."""

from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from agent.graph import build_graph
from agent.runner import persist_state
from agent.state import AssetMarketState, ThesisCandidate
from db.models import AgentRuntime, Asset, Base, Decision, DecisionReceipt, Outcome


def _noop_perceive(state):
    return state


def _fake_interpret(candidates, degraded):
    def _run(state):
        state["candidates"] = candidates
        state["llm_degraded"] = degraded
        state["memory_context"] = {}
        return state

    return _run

FAKE_CANDIDATES = [
    ThesisCandidate(
        asset="btcusdt",
        direction="long",
        thesis="Momentum test thesis",
        expected_edge_bps=50.0,
        confidence=0.8,
        time_horizon_minutes=30,
        risk_flags=[],
    )
]


def make_test_session():
    engine = create_engine("sqlite:///:memory:")
    tables = [t for t in Base.metadata.sorted_tables if t.name != "memory_embeddings"]
    Base.metadata.create_all(engine, tables=tables)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def seed_asset(session) -> Asset:
    asset = Asset(symbol="btcusdt", base_asset="btc", quote_asset="usdt", exchange="binance")
    session.add(asset)
    session.add(AgentRuntime(id=1, is_running=True, cycle=0, capital=100_000.0, equity=100_000.0, peak_equity=100_000.0))
    session.commit()
    return asset


def build_fake_state(cycle: int = 1):
    return {
        "cycle": cycle,
        "assets": {
            "btcusdt": AssetMarketState(
                symbol="btcusdt",
                price=100.0,
                volatility=0.02,
                depth=500_000,
                liquidity=1.0,
                trend=0.5,
                regime="normal",
                updated_at=datetime.now(timezone.utc).isoformat(),
                stale=False,
            )
        },
        "capital": 100_000.0,
        "equity": 100_000.0,
        "peak_equity": 100_000.0,
        "throttle": {},
        "config": {
            "kelly_fraction": 0.25,
            "max_position_pct": 0.12,
            "max_asset_exposure_pct": 0.20,
            "max_exposure_pct": 0.45,
            "drawdown_stop_pct": 0.08,
            "min_edge_over_cost_bps": 8.0,
            # Round-number thresholds matching this fixture's round-number
            # volatility/trend values — independent of config.py's real-data
            # calibrated defaults.
            "regime_high_volatility_threshold": 0.05,
            "regime_illiquid_liquidity_threshold": 0.5,
            "regime_trending_threshold": 0.7,
            "regime_mean_reverting_threshold": 0.3,
        },
        "candidates": [],
        "llm_degraded": False,
        "memory_context": {},
        "decisions": [],
        "positions": [],
        "closed_outcomes": [],
        "regime_changes": [],
        "throttle_updates": [],
        "pending_memory_writes": [],
    }


def test_full_cycle_persists_decision_receipt_and_outcome():
    test_app = build_graph(perceive=_noop_perceive, interpret=_fake_interpret(FAKE_CANDIDATES, False))

    session = make_test_session()
    seed_asset(session)

    state = build_fake_state()
    result = test_app.invoke(state)

    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]
    assert decision.accepted is True
    assert decision.size > 0

    persist_state(session, result)
    session.commit()

    decisions = list(session.scalars(select(Decision)))
    assert len(decisions) == 1
    assert decisions[0].accepted is True

    receipts = list(session.scalars(select(DecisionReceipt)))
    assert len(receipts) == 1
    assert "edge_over_cost" in receipts[0].checks
    assert "final_size" in receipts[0].sizing

    outcomes = list(session.scalars(select(Outcome)))
    assert len(outcomes) == 1
    assert outcomes[0].status == "open"
    assert outcomes[0].side == "long"


def test_llm_degraded_still_completes_cycle_with_no_new_decisions():
    test_app = build_graph(perceive=_noop_perceive, interpret=_fake_interpret([], True))

    session = make_test_session()
    seed_asset(session)

    state = build_fake_state()
    result = test_app.invoke(state)

    assert result["llm_degraded"] is True
    assert result["decisions"] == []

    persist_state(session, result)
    session.commit()

    assert list(session.scalars(select(Decision))) == []
    # regime classification and equity bookkeeping still ran despite the LLM outage.
    assert result["assets"]["btcusdt"].regime == "normal"
