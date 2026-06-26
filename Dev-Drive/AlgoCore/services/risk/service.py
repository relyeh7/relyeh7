import time
import logging
from datetime import datetime, timezone

from shared import events
from shared.config import settings
from shared.state import get_state, set_state, publish

logger = logging.getLogger(__name__)


class RiskService:
    _POLL_SEC = 10

    def __init__(self) -> None:
        self._day_start_pnl: float = 0.0
        self._current_day: int = 0

    def _daily_pnl_pct(self, total_pnl: float, portfolio_equity: float) -> float:
        today = datetime.now(timezone.utc).toordinal()
        if today != self._current_day:
            self._day_start_pnl = total_pnl
            self._current_day = today
        daily_pnl = total_pnl - self._day_start_pnl
        return round((daily_pnl / max(portfolio_equity, 1.0)) * 100, 4)

    def compute_risk(self) -> dict:
        perf_ml   = get_state("perf:ml") or {}
        perf_rl   = get_state("perf:rl") or {}
        positions = get_state("positions") or {}

        dd_ml = float(perf_ml.get("max_dd", 0.0))
        dd_rl = float(perf_rl.get("max_dd", 0.0))
        drawdown_pct = max(dd_ml, dd_rl)
        is_stopped   = drawdown_pct >= settings.stop_on_drawdown_pct
        open_count   = len(positions) if isinstance(positions, dict) else 0

        position_value = 0.0
        if isinstance(positions, dict):
            for symbol, pos in positions.items():
                price_state = get_state(f"price:{symbol}")
                price = (float(price_state["price"])
                         if price_state and "price" in price_state
                         else float(pos.get("entry_price", 0)))
                position_value += price * float(pos.get("size", 0))

        total_pnl        = float(perf_ml.get("total_pnl", 0.0)) + float(perf_rl.get("total_pnl", 0.0))
        initial_equity   = float(settings.initial_equity)
        portfolio_equity = max(initial_equity + total_pnl, 1.0)
        exposure_pct     = round((position_value / portfolio_equity) * 100, 4)
        daily_pnl_pct    = self._daily_pnl_pct(total_pnl, portfolio_equity)
        daily_pnl        = round(total_pnl - self._day_start_pnl, 4)

        return {
            "drawdown_pct":   round(drawdown_pct, 4),
            "is_stopped":     is_stopped,
            "exposure_pct":   exposure_pct,
            "open_positions": open_count,
            "daily_pnl_pct":  daily_pnl_pct,
            "daily_pnl":      daily_pnl,
            "total_equity":   round(portfolio_equity, 4),
        }

    def update(self) -> dict:
        risk = self.compute_risk()
        set_state("risk:state", risk)
        publish(events.RISK_UPDATE, risk)
        if risk["is_stopped"]:
            publish(events.RISK_ALERT, {
                "drawdown_pct": risk["drawdown_pct"],
                "action":       "STOP_TRADING",
                "reason":       f"Drawdown {risk['drawdown_pct']:.2f}% >= limit {settings.stop_on_drawdown_pct}%",
            })
        if risk["daily_pnl_pct"] <= -settings.daily_loss_limit_pct:
            publish(events.RISK_ALERT, {
                "daily_pnl_pct": risk["daily_pnl_pct"],
                "action":        "STOP_TRADING",
                "reason":        f"Daily loss {abs(risk['daily_pnl_pct']):.2f}% >= limit {settings.daily_loss_limit_pct}%",
            })
        logger.info(
            f"[Risk] dd={risk['drawdown_pct']:.2f}% daily={risk['daily_pnl_pct']:+.2f}% stopped={risk['is_stopped']}"
        )
        return risk

    def run(self) -> None:
        logger.info("[RiskService] Starting")
        while True:
            try:
                self.update()
            except Exception as exc:
                logger.error(f"[RiskService] error: {exc}")
            time.sleep(self._POLL_SEC)


if __name__ == "__main__":
    RiskService().run()
