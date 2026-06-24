import uuid
from datetime import datetime, timezone

from shared import events
from shared.state import get_state, publish


class PaperEngine:
    def __init__(self, slippage_pct: float = 0.001):
        self._slippage = slippage_pct

    def fill(self, decision: dict, current_price: float) -> dict:
        action = decision.get("action", "BUY").upper()
        side   = "buy" if action == "BUY" else "sell"
        mult   = 1 + self._slippage if side == "buy" else 1 - self._slippage
        fill_price = round(current_price * mult, 6)

        fill = {
            "symbol":    decision.get("symbol", "BTCUSDT"),
            "side":      side,
            "price":     fill_price,
            "size":      float(decision.get("size", 0.01)),
            "strategy":  decision.get("strategy", "orchestrator"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id":  str(uuid.uuid4()),
        }
        publish(events.ORDER_PLACED, {**fill, "status": "paper_filled"})
        publish(events.ORDER_FILLED, fill)
        return fill

    def run_once(self, decision: dict) -> dict | None:
        symbol = decision.get("symbol", "BTCUSDT")
        try:
            price_data = get_state(f"price:{symbol}")
            if not price_data:
                return None
            current_price = float(price_data.get("price", 0))
            if current_price <= 0:
                return None
            return self.fill(decision, current_price)
        except Exception:
            return None
