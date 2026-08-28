from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

class ThesisCandidate(BaseModel):
    asset: str
    direction: str = Field(description="'long', 'short', or 'no_action'")
    thesis: str = Field(description="Short natural-language rationale")
    expected_edge_bps: float
    confidence: float = Field(ge=0.0, le=1.0)
    time_horizon_minutes: int
    risk_flags: List[str] = Field(default_factory=list)

class AssetMarketState(BaseModel):
    symbol: str
    price: float
    volatility: float
    depth: float
    liquidity: float
    trend: float
    regime: str = "normal"
    updated_at: str

class DecisionReceipt(BaseModel):
    id: int
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
    created_at: str
    checks: Dict[str, bool] = Field(default_factory=dict)
    sizing: Dict[str, Any] = Field(default_factory=dict)

class Position(BaseModel):
    id: int
    asset: str
    side: str
    size: float
    entry_price: float
    unrealized_pnl: float = 0.0
    opened_at: str

class AgentState(TypedDict):
    cycle: int
    assets: Dict[str, AssetMarketState]
    capital: float
    equity: float
    peak_equity: float
    throttle: Dict[str, Dict[str, float]] # asset -> regime -> multiplier
    config: Dict[str, float]
    
    # Internal to loop
    candidates: List[ThesisCandidate]
    decisions: List[DecisionReceipt]
    positions: List[Position]
    history: List[Dict[str, Any]]
