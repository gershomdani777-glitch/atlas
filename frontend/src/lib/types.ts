export type Regime = "trending" | "mean_reverting" | "high_volatility" | "illiquid" | "normal";
export type Direction = "long" | "short" | "no_action";

export interface MarketAsset {
  symbol: string;
  price: number;
  volatility: number;
  liquidity: number;
  depth: number;
  trend: number;
  regime: Regime;
  stale: boolean;
  updated_at: string | null;
}

export interface Position {
  id: number;
  asset: string;
  side: string;
  size: number;
  entry_price: number;
  opened_at: string;
}

export interface Portfolio {
  capital: number;
  equity: number;
  peak_equity: number;
  exposure: number;
  positions: Position[];
}

export interface Decision {
  id: number;
  cycle: number;
  asset: string;
  direction: Direction;
  thesis: string;
  expected_edge_bps: number;
  confidence: number;
  regime: Regime;
  accepted: boolean;
  size: number;
  reason: string;
  created_at: string;
}

export interface DecisionReceipt {
  decision: Decision;
  inputs_snapshot: Record<string, unknown>;
  checks: Record<string, boolean>;
  sizing: Record<string, number>;
  memory_context: unknown;
}

export interface RiskConfig {
  max_position_pct: number;
  max_exposure_pct: number;
  max_asset_exposure_pct: number;
  drawdown_stop_pct: number;
  kelly_fraction: number;
  min_edge_over_cost_bps: number;
}

export interface EquitySnapshot {
  cycle: number;
  equity: number;
  capital: number;
  peak_equity: number;
  drawdown_pct: number;
  created_at: string;
}

export interface ThrottlePoint {
  asset: string;
  thesis_type: string;
  regime: string;
  multiplier: number;
  cycle: number;
}

export interface Metrics {
  equity_history: EquitySnapshot[];
  throttle_history: ThrottlePoint[];
  accepted: number;
  rejected: number;
}

export interface AgentStatus {
  running: boolean;
  cycle: number;
  cadence_seconds: number;
}

// WebSocket message shapes (discriminated on `type`)
export type LiveMessage =
  | { type: "snapshot"; running: boolean; cycle: number; capital: number; equity: number; peak_equity: number; positions: Position[]; recent_decisions: Decision[] }
  | { type: "tick"; symbol: string; price: number }
  | { type: "regime"; asset: string; previous_regime: Regime; new_regime: Regime; cycle: number }
  | { type: "decision"; decision: Decision };
