from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from db import repository
from db.session import get_session

router = APIRouter()


class RiskConfigUpdate(BaseModel):
    # Bounded so this safety-critical config can never be pushed into a
    # nonsensical or dangerous state (e.g. negative drawdown limit, >100%
    # Kelly sizing) via the public API.
    max_position_pct: float | None = Field(default=None, gt=0, le=1)
    max_exposure_pct: float | None = Field(default=None, gt=0, le=1)
    max_asset_exposure_pct: float | None = Field(default=None, gt=0, le=1)
    drawdown_stop_pct: float | None = Field(default=None, gt=0, le=1)
    kelly_fraction: float | None = Field(default=None, gt=0, le=1)
    min_edge_over_cost_bps: float | None = Field(default=None, ge=0)


@router.get("/config/risk")
def get_risk_config():
    with get_session() as session:
        return repository.get_risk_config(session)


@router.put("/config/risk")
def put_risk_config(update: RiskConfigUpdate):
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    with get_session() as session:
        return repository.update_risk_config(session, updates)
