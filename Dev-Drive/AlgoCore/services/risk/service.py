import time
import logging

from shared import events
from shared.config import settings
from shared.state import get_state, set_state, publish

logger = logging.getLogger(__name__)


class RiskService:
    _POLL_SEC = 10

    def compute_risk(self) -> dict:
        perf_ml   = get_state("perf:ml") or {}
        perf_rl   = get_state("perf:rl") or {}
        positions = get_state("positions") or {}

        dd_ml = float(perf_ml.get("max_dd", 0.0))
        dd_rl = float(perf_rl.get("max_dd", 0.0))
        drawdown_pct = max(dd_ml, dd_rl)
        is_stopped   = drawdown_pct >= settings.stop_on_drawdown_pct
        open_count   = len(positions) if isinstance(positions, dict) else 0

        # Real exposure_pct: current position value as % of portfolio equity
        position_value = 0.0
        if isinstance(positions, dict):
            for symbol, pos in positions.items():
                if not isinstance(pos, dict):
                    continue
                price_state = get_state(f"price:{symbol}")
                price = (float(price_state["price"])
                         if price_state and "price" in price_state
                         else float(pos.get("entry_price", 0)))
                position_value += price * float(pos.get("size", 0))

        total_pnl        = float(perf_ml.get("total_pnl", 0.0)) + float(perf_rl.get("total_pnl", 0.0))
        initial_equity   = float(getattr(settings, "initial_equity", 10_000.0))
        portfolio_equity = max(initial_equity + total_pnl, 1.0)
        exposure_pct     = round((position_value / portfolio_equity) * 100, 4)

        return {
            "drawdown_pct":   round(drawdown_pct, 4),
            "is_stopped":     is_stopped,
            "exposure_pct":   exposure_pct,
            "open_positions": open_count,
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
        logger.info(f"[Risk] dd={risk['drawdown_pct']:.2f}% stopped={risk['is_stopped']}")
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
