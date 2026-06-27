from fastapi import APIRouter
from shared.state import get_state
from shared.config import settings

router = APIRouter()


@router.get("/status")
def get_status():
    risk = get_state("risk:state") or {}
    prices: dict[str, float] = {}
    for symbol in settings.trading_symbols:
        price_state = get_state(f"price:{symbol}")
        if price_state and "price" in price_state:
            prices[symbol] = float(price_state["price"])
    return {
        "services": {"risk": "up", "data": "up"},
        "risk": {
            "drawdown_pct": risk.get("drawdown_pct", 0.0),
            "is_stopped": risk.get("is_stopped", False),
            "exposure_pct": risk.get("exposure_pct", 0.0),
        },
        "prices": prices,
    }
