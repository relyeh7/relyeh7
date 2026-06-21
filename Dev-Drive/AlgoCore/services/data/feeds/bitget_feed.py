import json
import time
import threading
import websocket
from datetime import datetime, timezone
from shared import events
from shared.state import publish
from shared.config import settings


class BitgetFeed:
    WS_URL = "wss://ws.bitget.com/v2/ws/public"

    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self._ws = None

    def _on_message(self, msg: dict) -> None:
        data = msg.get("data")
        if not data or not isinstance(data, list):
            return
        for item in data:
            try:
                publish(events.PRICE_TICK, {
                    "symbol":    item["instId"],
                    "price":     float(item["last"]),
                    "volume":    float(item.get("vol24h", 0)),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "exchange":  "bitget",
                })
            except (KeyError, ValueError):
                pass

    def _on_raw(self, ws, raw):
        try:
            msg = json.loads(raw)
            self._on_message(msg)
        except json.JSONDecodeError:
            pass

    def start(self) -> None:
        """Conecta WebSocket y escucha indefinidamente con reconexión."""
        subs = [{"instType": "SPOT", "channel": "ticker", "instId": s}
                for s in self.symbols]
        while True:
            try:
                ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_open=lambda ws: ws.send(json.dumps({"op": "subscribe", "args": subs})),
                    on_message=self._on_raw,
                )
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"[BitgetFeed] Error: {e} — reconectando en 5s")
            time.sleep(5)
