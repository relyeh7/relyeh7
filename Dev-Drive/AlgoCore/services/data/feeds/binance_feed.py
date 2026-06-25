import json
import time
import websocket
from datetime import datetime, timezone
from shared import events
from shared.state import publish, set_state


class BinanceFeed:
    WS_BASE = "wss://stream.binance.com:9443/stream?streams="

    def __init__(self, symbols: list[str]):
        self.symbols = symbols

    def _on_message(self, msg: dict) -> None:
        try:
            symbol = msg["s"]
            tick   = {
                "symbol":    symbol,
                "price":     float(msg["c"]),
                "volume":    float(msg["v"]),
                "timestamp": datetime.fromtimestamp(
                    msg["T"] / 1000, tz=timezone.utc
                ).isoformat(),
                "exchange":  "binance",
            }
            set_state(f"price:{symbol}", tick)
            publish(events.PRICE_TICK, tick)
        except (KeyError, ValueError):
            pass

    def _on_raw(self, ws, raw):
        try:
            outer = json.loads(raw)
            self._on_message(outer.get("data", outer))
        except json.JSONDecodeError:
            pass

    def start(self) -> None:
        streams = "/".join(f"{s.lower()}@miniTicker" for s in self.symbols)
        url = self.WS_BASE + streams
        while True:
            try:
                ws = websocket.WebSocketApp(url, on_message=self._on_raw)
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"[BinanceFeed] Error: {e} — reconectando en 5s")
            time.sleep(5)
