from unittest.mock import patch, MagicMock


def test_all_phase6_modules_import():
    from shared.config import settings
    from services.data.feeds.rest_poller import RestPriceFeed
    from services.risk.service import RiskService
    from services.risk.gate import RiskGate
    from services.sltp.manager import SLTPManager
    from services.sizing.kelly import KellySizer
    assert hasattr(settings, "stop_loss_pct")
    assert hasattr(settings, "take_profit_pct")
    assert hasattr(settings, "kelly_fraction")
    assert hasattr(settings, "feed_poll_sec")
    assert settings.stop_loss_pct > 0
    assert settings.kelly_fraction > 0


def test_rest_price_feed_poll_once():
    mock_router = MagicMock()
    mock_router.get_ticker.return_value = 65000.0
    with patch("services.data.feeds.rest_poller.set_state"), \
         patch("services.data.feeds.rest_poller.publish"):
        from services.data.feeds.rest_poller import RestPriceFeed
        feed = RestPriceFeed(router=mock_router, symbols=["BTCUSDT"], poll_sec=30)
        ticks = feed.poll_once()
    assert len(ticks) == 1
    assert ticks[0]["symbol"] == "BTCUSDT"
    assert ticks[0]["price"] == 65000.0


def test_risk_service_compute_and_update():
    perf = {"n_trades": 10, "win_rate": 0.6, "sharpe": 1.2,
            "max_dd": 3.5, "total_pnl": 80.0}
    def mock_get_state(key):
        if key == "positions":
            return {}
        return perf

    with patch("services.risk.service.get_state", side_effect=mock_get_state), \
         patch("services.risk.service.set_state"), \
         patch("services.risk.service.publish") as mock_pub, \
         patch("services.risk.service.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        mock_s.max_exposure_pct     = 90.0
        mock_s.initial_equity       = 10_000.0
        from services.risk.service import RiskService
        rs = RiskService()
        risk = rs.update()
    assert risk["drawdown_pct"] == 3.5
    assert risk["is_stopped"] is False
    from shared import events
    channels = [c[0][0] for c in mock_pub.call_args_list]
    assert events.RISK_UPDATE in channels
    assert events.RISK_ALERT not in channels


def test_risk_gate_integration():
    from services.risk.gate import RiskGate
    gate = RiskGate()

    risk_stopped = {"is_stopped": True, "drawdown_pct": 7.0, "open_positions": 1}
    with patch("services.risk.gate.get_state", return_value=risk_stopped):
        assert gate.is_blocked() is True

    risk_normal = {"is_stopped": False, "drawdown_pct": 2.0, "open_positions": 0}
    with patch("services.risk.gate.get_state", return_value=risk_normal), \
         patch("services.risk.gate.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        assert gate.is_blocked() is False


def test_sltp_stop_loss_triggers_sell():
    positions = {
        "BTCUSDT": {"symbol": "BTCUSDT", "side": "buy",
                    "entry_price": 50000.0, "size": 0.01, "strategy": "ml"}
    }
    tick = {"symbol": "BTCUSDT", "price": 48500.0}  # -3% → SL hit at 2%
    with patch("services.sltp.manager.get_state", return_value=positions), \
         patch("services.sltp.manager.publish"):
        from services.sltp.manager import SLTPManager
        mgr = SLTPManager(stop_loss_pct=2.0, take_profit_pct=4.0)
        decisions = mgr.process_tick(tick)
    assert len(decisions) == 1
    assert decisions[0]["action"] == "SELL"
    assert decisions[0]["reason"] == "sltp"


def test_kelly_sizer_computes_valid_size():
    perf = {"n_trades": 20, "win_rate": 0.6, "max_dd": 3.0,
            "total_pnl": 100.0, "sharpe": 1.5, "profit_factor": 2.0}
    with patch("services.sizing.kelly.get_state", return_value=perf), \
         patch("services.sizing.kelly.settings") as mock_s:
        mock_s.kelly_fraction = 0.25
        from services.sizing.kelly import KellySizer
        sizer = KellySizer(min_size=0.001)
        size = sizer.compute("ml")
    assert 0.001 <= size <= 0.25
