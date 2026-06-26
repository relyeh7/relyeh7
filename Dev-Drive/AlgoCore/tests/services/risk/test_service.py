from unittest.mock import patch


def _perf(max_dd: float = 3.0, n_trades: int = 5) -> dict:
    return {"n_trades": n_trades, "win_rate": 0.6, "sharpe": 1.2,
            "max_dd": max_dd, "total_pnl": 50.0}


def test_compute_risk_returns_expected_keys():
    perf = _perf(2.0)
    def mock_get_state(key):
        if key == "positions":
            return {}
        return perf

    with patch("services.risk.service.get_state", side_effect=mock_get_state), \
         patch("services.risk.service.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        mock_s.initial_equity       = 10_000.0
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
    def mock_get_state(key):
        if key == "positions":
            return {}
        return perf

    with patch("services.risk.service.get_state", side_effect=mock_get_state), \
         patch("services.risk.service.set_state"), \
         patch("services.risk.service.publish") as mock_pub, \
         patch("services.risk.service.settings") as mock_settings:
        mock_settings.stop_on_drawdown_pct = 6.0
        mock_settings.max_exposure_pct     = 90.0
        mock_settings.initial_equity       = 10_000.0
        mock_settings.daily_loss_limit_pct = 5.0
        from services.risk.service import RiskService
        rs = RiskService()
        rs.update()
    channels = [call[0][0] for call in mock_pub.call_args_list]
    assert "risk:update" in channels
    assert "risk:alert" in channels


def test_update_no_alert_when_drawdown_below_threshold():
    perf = _perf(max_dd=2.0)
    def mock_get_state(key):
        if key == "positions":
            return {}
        return perf

    with patch("services.risk.service.get_state", side_effect=mock_get_state), \
         patch("services.risk.service.set_state"), \
         patch("services.risk.service.publish") as mock_pub, \
         patch("services.risk.service.settings") as mock_settings:
        mock_settings.stop_on_drawdown_pct = 6.0
        mock_settings.max_exposure_pct     = 90.0
        mock_settings.initial_equity       = 10_000.0
        mock_settings.daily_loss_limit_pct = 5.0
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
    assert abs(risk["exposure_pct"] - round(5200 / 11000 * 100, 4)) < 0.01


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


def test_compute_risk_includes_daily_pnl_pct():
    """compute_risk() must return daily_pnl_pct field."""
    import services.risk.service as mod
    from unittest.mock import patch

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"):
        from services.risk.service import RiskService
        rs = RiskService()
        result = rs.compute_risk()

    assert "daily_pnl_pct" in result, "compute_risk must include daily_pnl_pct"
    assert isinstance(result["daily_pnl_pct"], float)


def test_daily_pnl_pct_resets_at_midnight():
    """_daily_pnl_pct must reset baseline when UTC day changes."""
    import services.risk.service as mod
    from unittest.mock import patch
    from services.risk.service import RiskService

    with patch.object(mod, "get_state", return_value=None):
        rs = RiskService()
        # Simulate day 1: total_pnl=100 (baseline set to 100)
        rs._current_day = 1
        rs._day_start_pnl = 100.0
        # On day 2, baseline should reset to current total_pnl
        rs._current_day = 0  # force a day change by setting current_day != today
        pct = rs._daily_pnl_pct(200.0)  # new day, baseline = 200, daily_pnl = 0

    assert pct == 0.0, f"After day reset, daily_pnl_pct must be 0.0, got {pct}"


def test_update_publishes_daily_loss_alert():
    """update() must publish RISK_ALERT when daily loss exceeds daily_loss_limit_pct."""
    import services.risk.service as mod
    from unittest.mock import patch
    from datetime import datetime, timezone
    from shared import events
    from services.risk.service import RiskService

    published = []

    def fake_get_state(key):
        if key == "perf:ml":
            return {"total_pnl": -600.0, "max_dd": 0.0}
        elif key == "perf:rl":
            return {"total_pnl": 0.0, "max_dd": 0.0}
        return None

    with patch.object(mod, "get_state", side_effect=fake_get_state), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish", side_effect=lambda ch, p: published.append((ch, p))), \
         patch.object(mod, "settings") as mock_settings:
        mock_settings.stop_on_drawdown_pct = 6.0
        mock_settings.initial_equity = 10_000.0
        mock_settings.daily_loss_limit_pct = 5.0
        rs = RiskService()
        # Set baseline to 0 and current_day to today, so daily_pnl = -600 - 0 = -600
        today = datetime.now(timezone.utc).toordinal()
        rs._current_day = today
        rs._day_start_pnl = 0.0
        rs.update()

    alert_payloads = [p for ch, p in published if ch == events.RISK_ALERT]
    daily_loss_alerts = [p for p in alert_payloads if "daily_pnl_pct" in p]
    assert daily_loss_alerts, "RISK_ALERT with daily_pnl_pct must be published when daily loss exceeds limit"
