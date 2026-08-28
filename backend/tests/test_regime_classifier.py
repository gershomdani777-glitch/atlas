import pytest

from agent.nodes import classify_regime
from agent.state import AssetMarketState


def _state_with(asset: AssetMarketState):
    return {
        "cycle": 1,
        "assets": {asset.symbol: asset},
        "regime_changes": [],
    }


def _asset(**overrides) -> AssetMarketState:
    defaults = dict(
        symbol="btcusdt",
        price=100.0,
        volatility=0.02,
        depth=500_000,
        liquidity=1.0,
        trend=0.5,
        updated_at="2026-01-01T00:00:00+00:00",
        stale=False,
    )
    defaults.update(overrides)
    return AssetMarketState(**defaults)


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"volatility": 0.049}, "normal"),
        ({"volatility": 0.051}, "high_volatility"),
        ({"liquidity": 0.51}, "normal"),
        ({"liquidity": 0.49}, "illiquid"),
        ({"trend": 0.69}, "normal"),
        ({"trend": 0.71}, "trending"),
        ({"trend": 0.31}, "normal"),
        ({"trend": 0.29}, "mean_reverting"),
        ({}, "normal"),
        ({"stale": True}, "illiquid"),
    ],
)
def test_regime_thresholds(overrides, expected):
    state = _state_with(_asset(**overrides))
    result = classify_regime(state)
    assert result["assets"]["btcusdt"].regime == expected


def test_regime_change_is_recorded():
    asset = _asset(volatility=0.06)
    asset.regime = "normal"  # simulate previous cycle's label
    state = _state_with(asset)
    result = classify_regime(state)
    assert len(result["regime_changes"]) == 1
    change = result["regime_changes"][0]
    assert change.previous_regime == "normal"
    assert change.new_regime == "high_volatility"


def test_no_regime_change_when_label_unchanged():
    asset = _asset()
    asset.regime = "normal"
    state = _state_with(asset)
    result = classify_regime(state)
    assert result["regime_changes"] == []
