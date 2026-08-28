from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from db import repository
from db.session import get_session

router = APIRouter()


class RiskConfigUpdate(BaseModel):
    max_position_pct: float | None = None
    max_exposure_pct: float | None = None
    max_asset_exposure_pct: float | None = None
    drawdown_stop_pct: float | None = None
    kelly_fraction: float | None = None
    min_edge_over_cost_bps: float | None = None


@router.get("/config/risk")
def get_risk_config():
    with get_session() as session:
        return repository.get_risk_config(session)


@router.put("/config/risk")
def put_risk_config(update: RiskConfigUpdate):
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    with get_session() as session:
        return repository.update_risk_config(session, updates)
