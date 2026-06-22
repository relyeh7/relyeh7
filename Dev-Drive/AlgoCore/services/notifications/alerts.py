import time
from shared import events
from shared.state import subscribe_once
from services.notifications.telegram import TelegramClient


class AlertSubscriber:
    POLL_SEC = 5

    def __init__(self, client: TelegramClient, max_iterations: int | None = None):
        self._client   = client
        self._max_iter = max_iterations
        self._last_ids = {
            events.RISK_ALERT:    "0",
            events.ORDER_FILLED:  "0",
            events.ORCH_DECISION: "0",
        }

    def listen(self) -> None:
        print("[Alerts] Starting Telegram alert subscriber")
        iterations = 0
        while self._max_iter is None or iterations < self._max_iter:
            self._poll()
            time.sleep(self.POLL_SEC)
            iterations += 1

    def _poll(self) -> None:
        for channel, last_id in self._last_ids.items():
            for payload in subscribe_once(channel, last_id=last_id):
                msg = self._format(channel, payload)
                if msg:
                    self._client.send(msg)

    @staticmethod
    def _format(channel: str, payload: dict) -> str | None:
        if channel == events.RISK_ALERT:
            level = payload.get("level", "")
            dd    = payload.get("drawdown_pct", 0)
            return f"RISK ALERT — {level}\nDrawdown: {dd:.2f}%"
        if channel == events.ORDER_FILLED:
            sym  = payload.get("symbol", "?")
            side = payload.get("side", "?").upper()
            px   = payload.get("price", 0)
            return f"ORDER FILLED\n{sym} {side} @ ${px:.2f}"
        if channel == events.ORCH_DECISION:
            action = payload.get("action", "?")
            reason = payload.get("reason", "")
            conf   = payload.get("confidence", 0)
            if action in ("STOP_ALL", "PAUSE_STRATEGY"):
                return f"ORCHESTRATOR: {action}\n{reason}\nConf: {conf:.0%}"
            return None
        return None
