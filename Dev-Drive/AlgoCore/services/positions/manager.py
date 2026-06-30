import time
from datetime import datetime, timezone

from shared.models import Trade, Position, Side
from shared import events
from shared.state import get_state, set_state, publish, subscribe_since
from services.journal.trade_journal import TradeJournal

_FEE = 0.001


class PositionManager:
    def __init__(self, journal: TradeJournal):
        self._journal    = journal
        self._positions: dict[str, Position] = {}
        self._journal.ensure_positions_table()
        self._load_from_redis()

    def _load_from_redis(self) -> None:
        raw = get_state("positions")
        if raw and isinstance(raw, dict):
            for symbol, data in raw.items():
                self._positions[symbol] = Position.model_validate(data)
            return
        # Redis miss — recover from PostgreSQL
        for symbol, pos in self._journal.get_open_positions():
            self._positions[symbol] = pos
        if self._positions:
            self._save_to_redis()

    def _save_to_redis(self) -> None:
        payload = {k: v.model_dump(mode="json") for k, v in self._positions.items()}
        set_state("positions", payload)
        publish(events.POSITION_UPDATE, payload)

    def on_fill(self, fill: dict) -> Trade | None:
        symbol   = fill["symbol"]
        side     = fill["side"].lower()
        price    = float(fill["price"])
        size     = float(fill["size"])
        strategy = fill.get("strategy", "unknown")
        ts       = datetime.now(timezone.utc)

        if side == "buy":
            pos = Position(
                symbol=symbol, side=Side.BUY,
                entry_price=price, size=size,
                strategy=strategy, opened_at=ts,
            )
            self._positions[symbol] = pos
            self._save_to_redis()
            self._journal.save_position(symbol, pos)
            return None

        if side == "sell" and symbol in self._positions:
            pos   = self._positions.pop(symbol)
            pnl   = (price - pos.entry_price) * pos.size * (1 - _FEE)
            trade = Trade(
                symbol=symbol, side=Side.BUY,
                entry_price=pos.entry_price, exit_price=price,
                size=pos.size, pnl=round(pnl, 6),
                strategy=pos.strategy,
                opened_at=pos.opened_at, closed_at=ts,
            )
            self._journal.save(trade)
            self._journal.delete_position(symbol)
            publish(events.TRADE_CLOSED, trade.model_dump(mode="json"))
            self._save_to_redis()
            return trade

        return None

    def get_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def run(self) -> None:
        last_id = "0"
        while True:
            fills, last_id = subscribe_since(events.ORDER_FILLED, last_id)
            for f in fills:
                self.on_fill(f)
            time.sleep(1)


if __name__ == "__main__":
    from shared.config import settings
    journal = TradeJournal(settings.postgres_url)
    journal.ensure_table()
    PositionManager(journal).run()
