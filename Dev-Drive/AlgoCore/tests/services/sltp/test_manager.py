from unittest.mock import patch, MagicMock


def test_check_position_triggers_stop_loss():
    from services.sltp.manager import SLTPManager
    mgr = SLTPManager(stop_loss_pct=2.0, take_profit_pct=4.0)
    # entry 50000, price dropped 2.1% → SL hit
    result = mgr.check_position("BTCUSDT", entry_price=50000.0, current_price=48950.0)
    assert result == "SELL"


def test_check_position_triggers_take_profit():
    from services.sltp.manager import SLTPManager
    mgr = SLTPManager(stop_loss_pct=2.0, take_profit_pct=4.0)
    # entry 50000, price up 4.1% → TP hit
    result = mgr.check_position("BTCUSDT", entry_price=50000.0, current_price=52050.0)
    assert result == "SELL"


def test_check_position_no_trigger_in_range():
    from services.sltp.manager import SLTPManager
    mgr = SLTPManager(stop_loss_pct=2.0, take_profit_pct=4.0)
    # entry 50000, price +1% — within range
    result = mgr.check_position("BTCUSDT", entry_price=50000.0, current_price=50500.0)
    assert result is None


def test_process_tick_publishes_sell_on_sl_hit():
    positions = {
        "BTCUSDT": {
            "symbol": "BTCUSDT", "side": "buy",
            "entry_price": 50000.0, "size": 0.01, "strategy": "ml",
            "opened_at": "2026-01-01T00:00:00Z",
        }
    }
    tick = {"symbol": "BTCUSDT", "price": 48000.0}  # -4% → SL hit at 2%

    with patch("services.sltp.manager.get_state", return_value=positions), \
         patch("services.sltp.manager.publish") as mock_pub:
        from services.sltp.manager import SLTPManager
        mgr = SLTPManager(stop_loss_pct=2.0, take_profit_pct=4.0)
        decisions = mgr.process_tick(tick)

    assert len(decisions) == 1
    assert decisions[0]["action"] == "SELL"
    assert decisions[0]["symbol"] == "BTCUSDT"
    mock_pub.assert_called_once()
    channel, payload = mock_pub.call_args[0]
    from shared import events
    assert channel == events.ORCH_DECISION


def test_process_tick_no_action_when_no_position():
    tick = {"symbol": "ETHUSDT", "price": 2800.0}
    with patch("services.sltp.manager.get_state", return_value={}), \
         patch("services.sltp.manager.publish") as mock_pub:
        from services.sltp.manager import SLTPManager
        mgr = SLTPManager(stop_loss_pct=2.0, take_profit_pct=4.0)
        decisions = mgr.process_tick(tick)
    assert decisions == []
    mock_pub.assert_not_called()
