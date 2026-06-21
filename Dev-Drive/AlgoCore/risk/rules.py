from shared.models import RiskState
from shared.config import Settings


def check_drawdown(state: RiskState, config: Settings) -> str | None:
    """
    Evaluate drawdown level and return alert level or None.

    Thresholds:
    - drawdown_pct >= config.stop_on_drawdown_pct → "STOP"
    - drawdown_pct >= 4.0 → "CRITICAL"
    - drawdown_pct >= 2.0 → "WARNING"
    - else → None
    """
    dd = state.drawdown_pct
    if dd >= config.stop_on_drawdown_pct:
        return "STOP"
    if dd >= 4.0:
        return "CRITICAL"
    if dd >= 2.0:
        return "WARNING"
    return None


def check_exposure(state: RiskState, config: Settings) -> str | None:
    """
    Check if exposure exceeds max threshold.

    Returns "HIGH_EXPOSURE" if exposure_pct >= config.max_exposure_pct, else None.
    """
    if state.exposure_pct >= config.max_exposure_pct:
        return "HIGH_EXPOSURE"
    return None
