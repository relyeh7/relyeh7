import time
from shared import events
from shared.config import settings
from shared.models import RiskState
from shared.state import get_state, set_state, publish
from risk.rules import check_drawdown, check_exposure


class RiskService:
    """
    Risk monitoring service that runs continuously.

    - Reads RiskState from Redis every 10s
    - Applies risk rules (drawdown, exposure)
    - Publishes alerts to Redis streams
    - Updates state if STOP condition triggered
    """

    def run(self) -> None:
        """Start the service loop."""
        print("[RiskService] Iniciado — monitoreando cada 10s")
        while True:
            self._tick()
            time.sleep(10)

    def _tick(self) -> None:
        """Single monitoring tick: read state, apply rules, publish alerts."""
        raw = get_state("risk")
        if not raw:
            return
        state = RiskState.model_validate(raw)

        alerts = []
        if (level := check_drawdown(state, settings)):
            alerts.append({
                "type": "DRAWDOWN",
                "level": level,
                "value": state.drawdown_pct
            })
            if level == "STOP":
                state.is_stopped = True
                set_state("risk", state.model_dump())

        if (level := check_exposure(state, settings)):
            alerts.append({
                "type": "EXPOSURE",
                "level": level,
                "value": state.exposure_pct
            })

        for alert in alerts:
            publish(events.RISK_ALERT, alert)
            print(f"[RiskService] ALERT: {alert}")


if __name__ == "__main__":
    RiskService().run()
