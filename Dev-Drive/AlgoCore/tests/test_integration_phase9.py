from unittest.mock import patch


def test_risk_service_compute_risk_includes_daily_pnl_pct():
    """compute_risk() must include daily_pnl_pct — was always missing before Phase 9."""
    import services.risk.service as mod

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"):
        from services.risk.service import RiskService
        result = RiskService().compute_risk()

    assert "daily_pnl_pct" in result
    assert isinstance(result["daily_pnl_pct"], float)


def test_risk_service_daily_loss_alert_fires():
    """update() must publish RISK_ALERT with daily_pnl_pct when daily loss > limit."""
    from datetime import datetime, timezone
    import services.risk.service as mod
    from shared import events

    published = []

    def fake_get_state(key):
        # perf:ml reports total_pnl=-600 (6% loss on $10k equity = above 5% daily limit)
        if "perf" in key:
            return {"total_pnl": -600.0, "max_dd": 0.0}
        return None

    with patch.object(mod, "get_state", side_effect=fake_get_state), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish", side_effect=lambda ch, p: published.append((ch, p))):
        from services.risk.service import RiskService
        rs = RiskService()
        # Set _current_day to today's ordinal so no day-reset occurs,
        # and _day_start_pnl=0.0 so daily_pnl = -600 - 0 = -600 (-6% on $10k)
        rs._current_day = datetime.now(timezone.utc).toordinal()
        rs._day_start_pnl = 0.0
        rs.update()

    daily_alerts = [p for ch, p in published if ch == events.RISK_ALERT and "daily_pnl_pct" in p]
    assert daily_alerts, "RISK_ALERT with daily_pnl_pct must fire when daily loss exceeds limit"
    assert daily_alerts[0]["action"] == "STOP_TRADING"


def test_sltp_manager_short_tp_triggers_buy():
    """process_tick() must trigger BUY to close a SHORT position at take-profit."""
    import services.sltp.manager as mod

    short_pos = {"side": "sell", "entry_price": "50000", "size": "0.01", "strategy": "ml"}
    published = []

    with patch.object(mod, "get_state", return_value={"BTCUSDT": short_pos}), \
         patch.object(mod, "publish", side_effect=lambda ch, p: published.append(p)):
        from services.sltp.manager import SLTPManager
        mgr = SLTPManager(stop_loss_pct=2.0, take_profit_pct=4.0)
        # SHORT TP = 50000 * (1 - 0.04) = 48000; price 47000 < 48000 → TP hit
        result = mgr.process_tick({"symbol": "BTCUSDT", "price": "47000"})

    assert result, "process_tick must return decision for SHORT TP hit"
    assert result[0]["action"] == "BUY", f"Expected 'BUY' to close short, got {result[0]['action']!r}"


def test_risk_healthcheck_checks_state_key():
    """docker-compose.prod.yml risk healthcheck must check state:risk:state, not just ping."""
    import yaml
    import pathlib

    path = pathlib.Path(__file__).parents[1] / "docker-compose.prod.yml"
    data = yaml.safe_load(path.read_text())
    hc_test = data["services"]["risk"]["healthcheck"]["test"]
    hc_cmd = " ".join(hc_test) if isinstance(hc_test, list) else hc_test
    assert "state:risk:state" in hc_cmd, (
        "risk healthcheck must verify 'state:risk:state' key exists — found: " + hc_cmd
    )
