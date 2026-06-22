import time
from shared import events
from shared.config import settings
from shared.state import subscribe_once, get_state
from services.executor.crypto.router import ExchangeRouter


class ExecutorService:
    POLL_INTERVAL_SEC = 30

    def __init__(self):
        self._router = ExchangeRouter()
        self._last_id = "0"

    def _process_decisions(self) -> None:
        try:
            # Poll for new decisions from stream
            decisions = subscribe_once(events.ORCH_DECISION, self._last_id)
            for decision in decisions:
                if decision.get("action") == "BUY":
                    symbol = decision.get("symbol", "BTCUSDT")
                    price = decision.get("price", 0)
                    size = decision.get("size", 0.1)
                    order_id = self._router.place_order(symbol, "buy", price, size)
                    print(f"[Executor] BUY order placed: {order_id}")
                elif decision.get("action") == "SELL":
                    symbol = decision.get("symbol", "BTCUSDT")
                    price = decision.get("price", 0)
                    size = decision.get("size", 0.1)
                    order_id = self._router.place_order(symbol, "sell", price, size)
                    print(f"[Executor] SELL order placed: {order_id}")
        except Exception as e:
            print(f"[Executor] error processing decisions: {e}")

    def run(self) -> None:
        print("[Executor] Starting order execution loop")
        while True:
            try:
                # Poll for new decisions
                self._process_decisions()
            except Exception as e:
                print(f"[Executor] loop error: {e}")
            time.sleep(self.POLL_INTERVAL_SEC)


if __name__ == "__main__":
    ExecutorService().run()
