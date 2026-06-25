import time
import logging

from shared import events
from shared.config import settings
from shared.models import OrderState, Side
from shared.state import subscribe_once, publish
from services.executor.crypto.router import ExchangeRouter
from services.executor.crypto.tracker import OrderTracker
from services.paper.engine import PaperEngine
from services.risk.gate import RiskGate
from services.sizing.kelly import KellySizer

logger = logging.getLogger(__name__)

_ACTIVE = {"BUY", "SELL"}


class ExecutorService:
    POLL_INTERVAL_SEC = 30

    def __init__(
        self,
        paper_engine: PaperEngine  | None = None,
        router:       ExchangeRouter | None = None,
        tracker:      OrderTracker   | None = None,
    ):
        self._paper      = paper_engine or PaperEngine()
        self._router     = router  or ExchangeRouter()
        self._tracker    = tracker or OrderTracker(self._router)
        self._last_id    = "0"
        self._risk_gate  = RiskGate()
        self._sizer      = KellySizer()

    def _process_decisions(self) -> None:
        if self._risk_gate.is_blocked():
            logger.warning("[Executor] Risk gate BLOCKED — skipping decisions")
            return
        decisions = subscribe_once(events.ORCH_DECISION, last_id=self._last_id)
        for decision in decisions:
            action = decision.get("action", "")
            if action not in _ACTIVE:
                continue
            try:
                if settings.paper_trading:
                    fill = self._paper.run_once(decision)
                    if fill:
                        logger.info(
                            f"[Executor] paper fill: {fill['symbol']} "
                            f"{fill['side']} @ {fill['price']}"
                        )
                else:
                    symbol     = decision.get("symbol", "BTCUSDT")
                    price      = float(decision.get("price", 0))
                    raw_size   = float(decision.get("size", 0.01))
                    kelly_size = self._sizer.compute(decision.get("strategy", "orchestrator"))
                    size       = min(raw_size, kelly_size)
                    exchange   = decision.get("exchange", "bitget")
                    order_id = self._router.place_order(symbol, action.lower(), price, size)
                    order    = OrderState(
                        id=order_id, symbol=symbol,
                        side=Side.BUY if action == "BUY" else Side.SELL,
                        price=price, size=size, exchange=exchange,
                        strategy=decision.get("strategy", "orchestrator"),
                    )
                    self._tracker.track(order)
                    publish(events.ORDER_PLACED, order.model_dump(mode="json"))
                    logger.info(f"[Executor] order placed: {order_id}")
            except Exception as exc:
                logger.error(f"[Executor] rejected: {exc}")
                publish(events.ORDER_REJECTED, {
                    "action": action,
                    "error": str(exc),
                    "symbol": decision.get("symbol", ""),
                })

        if decisions:
            self._last_id = decisions[-1].get("timestamp", self._last_id)

    def run(self) -> None:
        logger.info(f"[Executor] Starting (paper_trading={settings.paper_trading})")
        while True:
            try:
                self._process_decisions()
                if not settings.paper_trading:
                    self._tracker.poll_fills()
            except Exception as exc:
                logger.error(f"[Executor] loop error: {exc}")
            time.sleep(self.POLL_INTERVAL_SEC)


if __name__ == "__main__":
    ExecutorService().run()
