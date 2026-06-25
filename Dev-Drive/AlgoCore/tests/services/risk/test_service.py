from unittest.mock import patch


def _perf(max_dd: float = 3.0, n_trades: int = 5) -> dict:
    return {"n_trades": n_trades, "win_rate": 0.6, "sharpe": 1.2,
            "max_dd": max_dd, "total_pnl": 50.0}


def test_compute_risk_returns_expected_keys():
    with patch("services.risk.service.get_state", return_value=_perf(2.0)):
        from services.risk.service import RiskService
        rs = RiskService()
        risk = rs.compute_risk()
    assert "drawdown_pct" in risk
    assert "is_stopped" in risk
    assert "exposure_pct" in risk
    assert "open_positions" in risk


def test_compute_risk_stopped_when_drawdown_exceeds_threshold():
    perf = _perf(max_dd=7.5)
    positions = {"BTCUSDT": {"symbol": "BTCUSDT", "entry_price": 50000.0, "size": 0.1}}
    def mock_get_state(key):
        if key.startswith("perf:"):
            return perf
        if key == "positions":
            return positions
        return None

    with patch("services.risk.service.get_state", side_effect=mock_get_state), \
         patch("services.risk.service.settings") as mock_settings:
        mock_settings.stop_on_drawdown_pct = 6.0
        mock_settings.max_exposure_pct     = 90.0
        from services.risk.service import RiskService
        rs = RiskService()
        risk = rs.compute_risk()
    assert risk["is_stopped"] is True
    assert risk["drawdown_pct"] == 7.5


def test_update_publishes_risk_alert_on_drawdown():
    perf = _perf(max_dd=8.0)
    with patch("services.risk.service.get_state", return_value=perf), \
         patch("services.risk.service.set_state"), \
         patch("services.risk.service.publish") as mock_pub, \
         patch("services.risk.service.settings") as mock_settings:
        mock_settings.stop_on_drawdown_pct = 6.0
        mock_settings.max_exposure_pct     = 90.0
        from services.risk.service import RiskService
        rs = RiskService()
        rs.update()
    channels = [call[0][0] for call in mock_pub.call_args_list]
    assert "risk:update" in channels
    assert "risk:alert" in channels


def test_update_no_alert_when_drawdown_below_threshold():
    perf = _perf(max_dd=2.0)
    with patch("services.risk.service.get_state", return_value=perf), \
         patch("services.risk.service.set_state"), \
         patch("services.risk.service.publish") as mock_pub, \
         patch("services.risk.service.settings") as mock_settings:
        mock_settings.stop_on_drawdown_pct = 6.0
        mock_settings.max_exposure_pct     = 90.0
        from services.risk.service import RiskService
        rs = RiskService()
        rs.update()
    channels = [call[0][0] for call in mock_pub.call_args_list]
    assert "risk:update" in channels
    assert "risk:alert" not in channels
