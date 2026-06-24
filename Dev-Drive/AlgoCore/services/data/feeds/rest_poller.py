import time
import logging
from datetime import datetime, timezone

from shared import events
from shared.state import set_state, publish

logger = logging.getLogger(__name__)


class RestPriceFeed:
    def __init__(self, router, symbols: list[str], poll_sec: int = 30):
        self._router   = router
        self._symbols  = symbols
        self._poll_sec = poll_sec

    def poll_once(self) -> list[dict]:
        ticks: list[dict] = []
        for symbol in self._symbols:
            try:
                price = self._router.get_ticker(symbol)
                tick  = {
                    "symbol":    symbol,
                    "price":     float(price),
                    "exchange":  "rest",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                set_state(f"price:{symbol}", tick)
                publish(events.PRICE_TICK, tick)
                ticks.append(tick)
            except Exception as exc:
                logger.warning(f"[RestPriceFeed] {symbol}: {exc}")
        return ticks

    def run(self) -> None:
        logger.info(f"[RestPriceFeed] polling {self._symbols} every {self._poll_sec}s")
        while True:
            self.poll_once()
            time.sleep(self._poll_sec)
