import time
from datetime import datetime, timezone

from shared import events
from shared.models import OrderState
from shared.state import get_state, set_state, publish
from services.executor.crypto.router import ExchangeRouter

_POLL_SEC = 30


class OrderTracker:
    def __init__(self, router: ExchangeRouter):
        self._router = router

    def track(self, order: OrderState) -> None:
        pending = get_state("pending_orders") or {}
        pending[order.id] = order.model_dump(mode="json")
        set_state("pending_orders", pending)

    def poll_fills(self) -> list[dict]:
        pending = get_state("pending_orders") or {}
        fills: list[dict] = []

        for order_id, data in list(pending.items()):
            try:
                status = self._router.get_order_status(
                    order_id, data["symbol"], data["exchange"]
                )
                if status == "filled":
                    fill_price = self._router.get_ticker(data["symbol"])
                    fill = {
                        "symbol":    data["symbol"],
                        "side":      data["side"],
                        "price":     fill_price,
                        "size":      data["size"],
                        "strategy":  data.get("strategy", "unknown"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "order_id":  order_id,
                    }
                    publish(events.ORDER_FILLED, fill)
                    del pending[order_id]
                    fills.append(fill)
                elif status == "cancelled":
                    del pending[order_id]
            except Exception:
                pass

        set_state("pending_orders", pending)
        return fills

    def run(self) -> None:
        while True:
            self.poll_fills()
            time.sleep(_POLL_SEC)
