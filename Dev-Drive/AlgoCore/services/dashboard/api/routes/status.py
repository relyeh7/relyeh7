from fastapi import APIRouter
from shared.state import get_state

router = APIRouter()


@router.get("/status")
def get_status():
    risk = get_state("risk") or {}
    prices = get_state("prices") or {}
    return {
        "services": {"risk": "up", "data": "up"},
        "risk": {
            "drawdown_pct": risk.get("drawdown_pct", 0.0),
            "is_stopped": risk.get("is_stopped", False),
            "exposure_pct": risk.get("exposure_pct", 0.0),
        },
        "prices": prices,
    }
