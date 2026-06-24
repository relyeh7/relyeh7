from shared.config import settings
from shared.state import get_state


class RiskGate:
    def __init__(self, state_key: str = "risk:state"):
        self._key = state_key

    def is_blocked(self) -> bool:
        risk = get_state(self._key)
        if not risk:
            return False
        if risk.get("is_stopped", False):
            return True
        dd = float(risk.get("drawdown_pct", 0.0))
        return dd >= settings.stop_on_drawdown_pct
