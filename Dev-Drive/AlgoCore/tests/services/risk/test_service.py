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


def test_compute_risk_exposure_pct_with_open_positions():
    positions = {
        "BTCUSDT": {"symbol": "BTCUSDT", "entry_price": 50000.0, "size": 0.1,
                    "side": "buy", "strategy": "ml"},
    }
    perf = {"n_trades": 5, "win_rate": 0.6, "max_dd": 2.0,
            "total_pnl": 500.0, "sharpe": 1.2, "profit_factor": 1.5}
    price_data = {"symbol": "BTCUSDT", "price": 52000.0, "exchange": "bitget"}

    def mock_get_state(key):
        if key.startswith("perf:"):
            return perf
        if key == "positions":
            return positions
        if key == "price:BTCUSDT":
            return price_data
        return None

    with patch("services.risk.service.get_state", side_effect=mock_get_state), \
         patch("services.risk.service.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        mock_s.initial_equity       = 10_000.0
        from services.risk.service import RiskService
        rs = RiskService()
        risk = rs.compute_risk()

    # position_value = 52000 * 0.1 = 5200
    # portfolio_equity = 10000 + 500 + 500 = 11000  (ml + rl both return perf)
    # exposure_pct = 5200 / 11000 * 100 = 47.27...
    assert risk["exposure_pct"] > 0.0
    assert risk["exposure_pct"] < 100.0


def test_compute_risk_exposure_falls_back_to_entry_price():
    positions = {
        "BTCUSDT": {"symbol": "BTCUSDT", "entry_price": 48000.0, "size": 0.05,
                    "side": "buy", "strategy": "ml"},
    }

    def mock_get_state(key):
        if key.startswith("perf:"):
            return {"total_pnl": 0.0, "max_dd": 0.0}
        if key == "positions":
            return positions
        return None  # no price:{symbol} state

    with patch("services.risk.service.get_state", side_effect=mock_get_state), \
         patch("services.risk.service.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        mock_s.initial_equity       = 10_000.0
        from services.risk.service import RiskService
        rs = RiskService()
        risk = rs.compute_risk()

    # falls back to entry_price: 48000 * 0.05 = 2400
    # exposure = 2400 / 10000 * 100 = 24.0
    assert abs(risk["exposure_pct"] - 24.0) < 0.01


def test_compute_risk_exposure_zero_when_no_positions():
    with patch("services.risk.service.get_state", return_value=None), \
         patch("services.risk.service.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        mock_s.initial_equity       = 10_000.0
        from services.risk.service import RiskService
        rs = RiskService()
        risk = rs.compute_risk()
    assert risk["exposure_pct"] == 0.0
