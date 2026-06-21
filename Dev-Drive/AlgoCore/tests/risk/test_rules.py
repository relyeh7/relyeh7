from shared.models import RiskState
from shared.config import Settings


def _settings(**kwargs) -> Settings:
    base = {"stop_on_drawdown_pct": 6.0, "max_daily_drawdown_pct": 6.0, "max_exposure_pct": 90.0}
    base.update(kwargs)
    return Settings(**base)


def test_no_alert_under_threshold():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=1.0)
    assert check_drawdown(state, _settings()) is None


def test_warning_at_2pct():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=2.5)
    assert check_drawdown(state, _settings()) == "WARNING"


def test_critical_at_4pct():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=4.5)
    assert check_drawdown(state, _settings()) == "CRITICAL"


def test_stop_at_6pct():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=6.1)
    assert check_drawdown(state, _settings()) == "STOP"


def test_exposure_alert():
    from risk.rules import check_exposure
    state = RiskState(total_equity=1000.0, exposure_pct=95.0)
    assert check_exposure(state, _settings()) == "HIGH_EXPOSURE"


def test_exposure_ok():
    from risk.rules import check_exposure
    state = RiskState(total_equity=1000.0, exposure_pct=80.0)
    assert check_exposure(state, _settings()) is None
