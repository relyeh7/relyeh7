import time
import logging
from datetime import datetime, timezone, date

from shared import events
from shared.state import get_state, subscribe_once
from services.notifications.telegram import TelegramClient

logger = logging.getLogger(__name__)


class AlertSubscriber:
    POLL_SEC = 5

    def __init__(self, client: TelegramClient | None = None, max_iterations: int | None = None):
        self._tg = client or TelegramClient()
        self._max_iter = max_iterations
        self._last_id_risk  = "0"
        self._last_id_trade = "0"
        self._last_summary_date: date | None = None
        # Legacy support for old _last_ids format
        self._last_ids = {
            events.RISK_ALERT: "0",
            events.ORDER_FILLED: "0",
            events.ORCH_DECISION: "0",
        }

    def on_trade_closed(self, trade: dict) -> None:
        pnl    = float(trade.get("pnl", 0))
        symbol = trade.get("symbol", "?")
        side   = trade.get("side", "?").upper()
        strat  = trade.get("strategy", "unknown")
        sign   = "WIN" if pnl >= 0 else "LOSS"
        msg    = f"[{sign}] Trade closed: {symbol} {side} P&L {pnl:+.4f} USDT (strategy: {strat})"
        try:
            self._tg.send(msg)
        except Exception as exc:
            logger.error(f"[Alerts] trade telegram error: {exc}")

    def on_risk_alert(self, alert: dict) -> None:
        dd     = float(alert.get("drawdown_pct", 0))
        action = alert.get("action", "UNKNOWN")
        msg    = f"[RISK] drawdown {dd:.1f}% — {action}"
        try:
            self._tg.send(msg)
        except Exception as exc:
            logger.error(f"[Alerts] risk telegram error: {exc}")

    def _send_daily_summary(self) -> None:
        today = datetime.now(timezone.utc).date()
        if self._last_summary_date == today:
            return
        self._last_summary_date = today
        perf_ml = get_state("perf:ml") or {}
        perf_rl = get_state("perf:rl") or {}
        ml_pnl  = perf_ml.get("total_pnl", 0.0)
        rl_pnl  = perf_rl.get("total_pnl", 0.0)
        msg = (
            f"[DAILY] {today}\n"
            f"ML  — trades: {perf_ml.get('n_trades', 0)}, "
            f"P&L: {ml_pnl:+.2f}, win: {perf_ml.get('win_rate', 0):.0%}\n"
            f"RL   — trades: {perf_rl.get('n_trades', 0)}, "
            f"P&L: {rl_pnl:+.2f}, win: {perf_rl.get('win_rate', 0):.0%}"
        )
        try:
            self._tg.send(msg)
        except Exception as exc:
            logger.error(f"[Alerts] daily summary telegram error: {exc}")

    def listen(self) -> None:
        """Legacy method: polling loop for old tests and existing code."""
        print("[Alerts] Starting Telegram alert subscriber")
        iterations = 0
        while self._max_iter is None or iterations < self._max_iter:
            self._poll()
            time.sleep(self.POLL_SEC)
            iterations += 1

    def _poll(self) -> None:
        """Legacy method: poll and handle multiple event types."""
        for channel, last_id in self._last_ids.items():
            for payload in subscribe_once(channel, last_id=last_id):
                msg = self._format(channel, payload)
                if msg:
                    self._tg.send(msg)

    @staticmethod
    def _format(channel: str, payload: dict) -> str | None:
        """Legacy method: format messages for old event types."""
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

    def run(self) -> None:
        """New method: modern polling loop with new event types."""
        logger.info("[Alerts] Starting alert subscriber")
        iterations = 0
        while self._max_iter is None or iterations < self._max_iter:
            risk_alerts = subscribe_once(events.RISK_ALERT, last_id=self._last_id_risk)
            for alert in risk_alerts:
                self.on_risk_alert(alert)
            if risk_alerts:
                self._last_id_risk = risk_alerts[-1].get("timestamp", self._last_id_risk)

            trades = subscribe_once(events.TRADE_CLOSED, last_id=self._last_id_trade)
            for trade in trades:
                self.on_trade_closed(trade)
            if trades:
                self._last_id_trade = trades[-1].get("timestamp", self._last_id_trade)

            self._send_daily_summary()
            time.sleep(10)
            iterations += 1


if __name__ == "__main__":
    AlertSubscriber().run()
