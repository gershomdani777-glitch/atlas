from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class ThesisCandidate(BaseModel):
    asset: str
    direction: str = Field(description="'long', 'short', or 'no_action'")
    thesis: str = Field(description="Short natural-language rationale")
    expected_edge_bps: float
    confidence: float = Field(ge=0.0, le=1.0)
    time_horizon_minutes: int = Field(ge=1)
    risk_flags: List[str] = Field(default_factory=list)


class ThesisCandidateList(BaseModel):
    candidates: List[ThesisCandidate] = Field(default_factory=list)


class AssetMarketState(BaseModel):
    symbol: str
    price: float
    volatility: float
    depth: float
    liquidity: float
    trend: float
    spread_bps: float = 0.0
    regime: str = "normal"
    updated_at: str
    stale: bool = False


class DecisionReceipt(BaseModel):
    id: int = 0
    cycle: int
    asset: str
    direction: str
    thesis: str
    expected_edge_bps: float
    confidence: float
    regime: str
    accepted: bool
    size: float
    reason: str
    time_horizon_minutes: int = 30
    created_at: str
    checks: Dict[str, bool] = Field(default_factory=dict)
    sizing: Dict[str, Any] = Field(default_factory=dict)
    inputs_snapshot: Dict[str, Any] = Field(default_factory=dict)
    memory_context: List[Dict[str, str]] = Field(default_factory=list)
    fill: Optional[Dict[str, float]] = None  # set by execute() for accepted decisions


class Position(BaseModel):
    id: int = 0  # DB order id once persisted
    outcome_id: int = 0  # DB outcome id once persisted
    decision_id: int = 0
    asset: str
    side: str
    size: float
    entry_price: float
    thesis: str
    time_horizon_minutes: int
    unrealized_pnl: float = 0.0
    opened_at: str


class ClosedOutcome(BaseModel):
    outcome_id: int
    decision_id: int
    asset: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    thesis: str
    regime: str
    realized_pnl: float
    realized_pnl_bps: float
    direction_correct: bool
    closed_at: str
    close_reason: str


class RegimeChange(BaseModel):
    asset: str
    previous_regime: str
    new_regime: str
    cycle: int


class ThrottleUpdate(BaseModel):
    asset: str
    thesis_type: str
    regime: str
    win_rate: float
    avg_edge_bps: float
    sample_count: int
    multiplier: float


class AgentState(TypedDict):
    cycle: int
    assets: Dict[str, AssetMarketState]
    capital: float
    equity: float
    peak_equity: float
    throttle: Dict[str, Dict[str, Dict[str, float]]]  # asset -> direction -> regime -> multiplier
    config: Dict[str, float]

    candidates: List[ThesisCandidate]
    llm_degraded: bool
    memory_context: Dict[str, List[Dict[str, str]]]  # asset -> retrieved (thesis, outcome) pairs used this cycle

    decisions: List[DecisionReceipt]  # new decisions produced this cycle
    positions: List[Position]  # currently open positions (existing + newly opened)
    closed_outcomes: List[ClosedOutcome]  # positions closed this cycle

    regime_changes: List[RegimeChange]
    throttle_updates: List[ThrottleUpdate]
    pending_memory_writes: List[Dict[str, str]]
