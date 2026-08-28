from __future__ import annotations

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 768  # matches Gemini's text-embedding-004

# JSONB on Postgres (indexable, binary), plain JSON elsewhere (e.g. the
# SQLite engine used by test_graph_integration.py).
PortableJSON = JSON().with_variant(JSONB, "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, index=True)
    base_asset: Mapped[str] = mapped_column(String)
    quote_asset: Mapped[str] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String, default="binance")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Last-known snapshot, refreshed once per agent cycle by runner.persist_state();
    # the API layer reads this instead of hitting Redis again on every REST call.
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    current_volatility: Mapped[float] = mapped_column(Float, default=0.0)
    current_liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    current_depth: Mapped[float] = mapped_column(Float, default=0.0)
    current_trend: Mapped[float] = mapped_column(Float, default=0.5)
    current_regime: Mapped[str] = mapped_column(String, default="normal")
    current_stale: Mapped[bool] = mapped_column(Boolean, default=True)
    snapshot_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle: Mapped[int] = mapped_column(Integer, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    direction: Mapped[str] = mapped_column(String)
    thesis: Mapped[str] = mapped_column(String)
    expected_edge_bps: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    regime: Mapped[str] = mapped_column(String)
    accepted: Mapped[bool] = mapped_column(Boolean)
    size: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    asset: Mapped["Asset"] = relationship()
    receipt: Mapped["DecisionReceipt"] = relationship(back_populates="decision", uselist=False)


class DecisionReceipt(Base):
    __tablename__ = "decision_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), unique=True)
    inputs_snapshot: Mapped[dict] = mapped_column(PortableJSON, default=dict)
    checks: Mapped[dict] = mapped_column(PortableJSON, default=dict)
    sizing: Mapped[dict] = mapped_column(PortableJSON, default=dict)
    memory_context: Mapped[dict] = mapped_column(PortableJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    decision: Mapped["Decision"] = relationship(back_populates="receipt")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    side: Mapped[str] = mapped_column(String)
    requested_size: Mapped[float] = mapped_column(Float)
    filled_size: Mapped[float] = mapped_column(Float)
    fill_price: Mapped[float] = mapped_column(Float)
    slippage_bps: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="filled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    side: Mapped[str] = mapped_column(String)
    entry_price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    time_horizon_minutes: Mapped[int] = mapped_column(Integer, default=30)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open", index=True)  # open | closed


class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    outcome_id: Mapped[int | None] = mapped_column(ForeignKey("outcomes.id"), nullable=True)
    thesis_text: Mapped[str] = mapped_column(String)
    outcome_summary: Mapped[str] = mapped_column(String, default="")
    regime: Mapped[str] = mapped_column(String)
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RiskConfig(Base):
    __tablename__ = "risk_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_key: Mapped[str] = mapped_column(String, unique=True)
    config_value: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str] = mapped_column(String, default="system")


class ThrottleStat(Base):
    __tablename__ = "throttle_stats"
    __table_args__ = (UniqueConstraint("asset_id", "thesis_type", "regime", name="uq_throttle_bucket"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    thesis_type: Mapped[str] = mapped_column(String)  # "long" | "short"
    regime: Mapped[str] = mapped_column(String)
    win_rate: Mapped[float] = mapped_column(Float, default=0.5)
    avg_edge_bps: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    throttle_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ThrottleHistory(Base):
    __tablename__ = "throttle_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    thesis_type: Mapped[str] = mapped_column(String)
    regime: Mapped[str] = mapped_column(String)
    multiplier: Mapped[float] = mapped_column(Float)
    cycle: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentRuntime(Base):
    """Singleton row (id=1) holding kill-switch + capital state across restarts."""

    __tablename__ = "agent_runtime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    is_running: Mapped[bool] = mapped_column(Boolean, default=True)
    cycle: Mapped[int] = mapped_column(Integer, default=0)
    capital: Mapped[float] = mapped_column(Float, default=100000.0)
    equity: Mapped[float] = mapped_column(Float, default=100000.0)
    peak_equity: Mapped[float] = mapped_column(Float, default=100000.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle: Mapped[int] = mapped_column(Integer, index=True)
    equity: Mapped[float] = mapped_column(Float)
    capital: Mapped[float] = mapped_column(Float)
    peak_equity: Mapped[float] = mapped_column(Float)
    drawdown_pct: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
