import time
import logging
from shared import events
from shared.config import settings
from shared.state import subscribe_once, get_state
from services.executor.crypto.router import ExchangeRouter

logger = logging.getLogger(__name__)


class ExecutorService:
    POLL_INTERVAL_SEC = 30

    def __init__(self):
        self._router = ExchangeRouter()
        self._last_id = "0"

    def _process_decisions(self) -> None:
        try:
            # Poll for new decisions from stream (keyword arg, not positional)
            decisions = subscribe_once(events.ORCH_DECISION, last_id=self._last_id)
            for decision in decisions:
                if decision.get("action") == "BUY":
                    symbol = decision.get("symbol", "BTCUSDT")
                    price = decision.get("price", 0)
                    size = decision.get("size", 0.1)
                    order_id = self._router.place_order(symbol, "buy", price, size)
                    logger.info(f"[Executor] BUY order placed: {order_id}")
                elif decision.get("action") == "SELL":
                    symbol = decision.get("symbol", "BTCUSDT")
                    price = decision.get("price", 0)
                    size = decision.get("size", 0.1)
                    order_id = self._router.place_order(symbol, "sell", price, size)
                    logger.info(f"[Executor] SELL order placed: {order_id}")

            # Update last ID so next poll only fetches newer messages
            if decisions:
                self._last_id = decisions[-1].get("timestamp", self._last_id)
        except Exception as e:
            logger.error(f"[Executor] error processing decisions: {e}")

    def run(self) -> None:
        logger.info("[Executor] Starting order execution loop")
        while True:
            try:
                # Poll for new decisions
                self._process_decisions()
            except Exception as e:
                logger.error(f"[Executor] loop error: {e}")
            time.sleep(self.POLL_INTERVAL_SEC)


if __name__ == "__main__":
    ExecutorService().run()
