import time
import logging
from datetime import datetime, timezone

from shared import events
from shared.config import settings
from shared.state import get_state, publish, subscribe_once

logger = logging.getLogger(__name__)


class SLTPManager:
    def __init__(
        self,
        stop_loss_pct:   float | None = None,
        take_profit_pct: float | None = None,
    ):
        self._sl_pct = stop_loss_pct  if stop_loss_pct   is not None else settings.stop_loss_pct
        self._tp_pct = take_profit_pct if take_profit_pct is not None else settings.take_profit_pct

    def check_position(self, symbol: str, entry_price: float, current_price: float) -> str | None:
        sl_price = entry_price * (1 - self._sl_pct / 100)
        tp_price = entry_price * (1 + self._tp_pct / 100)
        if current_price <= sl_price:
            logger.info(f"[SLTP] {symbol} SL hit: {current_price:.2f} <= {sl_price:.2f}")
            return "SELL"
        if current_price >= tp_price:
            logger.info(f"[SLTP] {symbol} TP hit: {current_price:.2f} >= {tp_price:.2f}")
            return "SELL"
        return None

    def process_tick(self, tick: dict) -> list[dict]:
        symbol        = tick.get("symbol", "")
        current_price = float(tick.get("price", 0))
        positions     = get_state("positions") or {}
        triggered: list[dict] = []

        if symbol not in positions:
            return triggered

        pos = positions[symbol]
        if pos.get("side", "").lower() != "buy":
            return triggered

        entry_price = float(pos.get("entry_price", 0))
        if entry_price <= 0 or current_price <= 0:
            return triggered

        action = self.check_position(symbol, entry_price, current_price)
        if action:
            decision = {
                "action":     action,
                "symbol":     symbol,
                "price":      str(current_price),
                "size":       str(pos.get("size", 0.01)),
                "strategy":   pos.get("strategy", "sltp"),
                "reason":     "sltp",
                "confidence": 1.0,
                "timestamp":  datetime.now(timezone.utc).isoformat(),
            }
            publish(events.ORCH_DECISION, decision)
            triggered.append(decision)

        return triggered

    def run(self) -> None:
        logger.info("[SLTPManager] Starting")
        last_id = "0"
        while True:
            ticks = subscribe_once(events.PRICE_TICK, last_id=last_id)
            for tick in ticks:
                self.process_tick(tick)
            if ticks:
                last_id = ticks[-1].get("timestamp", last_id)
            time.sleep(1)


if __name__ == "__main__":
    SLTPManager().run()
