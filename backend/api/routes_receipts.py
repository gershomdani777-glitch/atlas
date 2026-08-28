from fastapi import APIRouter, HTTPException

from db import repository
from db.session import get_session

router = APIRouter()


@router.get("/agent/decisions/{decision_id}/receipt")
def get_receipt(decision_id: int):
    with get_session() as session:
        receipt = repository.get_decision_receipt(session, decision_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return receipt
