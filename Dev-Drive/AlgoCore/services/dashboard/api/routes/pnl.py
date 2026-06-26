from fastapi import APIRouter
from shared.state import get_state

router = APIRouter()


@router.get("/pnl")
def get_pnl():
    risk = get_state("risk:state") or {}
    return {
        "total_equity": risk.get("total_equity", 0.0),
        "daily_pnl":    risk.get("daily_pnl", 0.0),
        "daily_pnl_pct": risk.get("daily_pnl_pct", 0.0),
        "drawdown_pct":  risk.get("drawdown_pct", 0.0),
    }
