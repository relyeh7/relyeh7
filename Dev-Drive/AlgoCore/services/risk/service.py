import time
import logging

from shared import events
from shared.config import settings
from shared.state import get_state, set_state, publish

logger = logging.getLogger(__name__)


class RiskService:
    _POLL_SEC = 10

    def compute_risk(self) -> dict:
        perf_ml = get_state("perf:ml") or {}
        perf_rl = get_state("perf:rl") or {}
        positions = get_state("positions") or {}

        dd_ml = float(perf_ml.get("max_dd", 0.0))
        dd_rl = float(perf_rl.get("max_dd", 0.0))
        drawdown_pct = max(dd_ml, dd_rl)
        is_stopped   = drawdown_pct >= settings.stop_on_drawdown_pct
        open_count   = len(positions) if isinstance(positions, dict) else 0

        return {
            "drawdown_pct":   round(drawdown_pct, 4),
            "is_stopped":     is_stopped,
            "exposure_pct":   0.0,
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
