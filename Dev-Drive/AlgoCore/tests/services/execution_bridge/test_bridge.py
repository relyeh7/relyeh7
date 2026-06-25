from unittest.mock import patch

_BUY_DECISION = {
    "action": "BUY", "confidence": 0.82, "market": "crypto",
    "exchange": "binance", "strategy": "ml", "capital_pct": 0.05,
    "reason": "ml signal", "timestamp": "2026-06-21T10:00:00Z",
}
_HOLD_DECISION = {
    "action": "HOLD", "confidence": 0.5, "market": "crypto",
    "exchange": "auto", "strategy": "ml", "capital_pct": 0.0,
    "reason": "no signal", "timestamp": "2026-06-21T10:00:00Z",
}
_STOP_DECISION = {
    "action": "STOP_ALL", "confidence": 0.95, "market": "crypto",
    "exchange": "auto", "strategy": "ml", "capital_pct": 0.0,
    "reason": "drawdown", "timestamp": "2026-06-21T10:00:00Z",
}

def test_bridge_publishes_on_buy_decision():
    with patch("services.execution_bridge.bridge.publish") as mock_pub, \
         patch("services.execution_bridge.bridge.subscribe_since", return_value=([_BUY_DECISION], "1")):
        from services.execution_bridge.bridge import ExecutionBridge
        bridge = ExecutionBridge("BTCUSDT", "binance")
        result = bridge._process(_BUY_DECISION)
    assert result is True
    mock_pub.assert_called_once()
    channel, payload = mock_pub.call_args[0]
    assert channel == "signal:new"
    assert payload["action"] == "BUY"
    assert payload["confidence"] == 0.82

def test_bridge_skips_hold_decision():
    with patch("services.execution_bridge.bridge.publish") as mock_pub:
        from services.execution_bridge.bridge import ExecutionBridge
        bridge = ExecutionBridge("BTCUSDT", "binance")
        result = bridge._process(_HOLD_DECISION)
    assert result is False
    mock_pub.assert_not_called()

def test_bridge_publishes_cancel_all_on_stop():
    with patch("services.execution_bridge.bridge.publish") as mock_pub:
        from services.execution_bridge.bridge import ExecutionBridge
        bridge = ExecutionBridge("BTCUSDT", "binance")
        result = bridge._process(_STOP_DECISION)
    assert result is True
    channel, payload = mock_pub.call_args[0]
    assert channel == "signal:new"
    assert payload["action"] == "CANCEL_ALL"

def test_bridge_maps_auto_exchange_to_bitget():
    with patch("services.execution_bridge.bridge.publish") as mock_pub:
        from services.execution_bridge.bridge import ExecutionBridge
        bridge = ExecutionBridge("BTCUSDT", "auto")
        decision = {**_BUY_DECISION, "exchange": "auto"}
        bridge._process(decision)
    _, payload = mock_pub.call_args[0]
    assert payload["exchange"] == "bitget"


def test_bridge_run_uses_subscribe_since():
    """Ensure run() uses subscribe_since — not subscribe_once with ISO-timestamp cursor."""
    from unittest.mock import patch, MagicMock
    import itertools
    import services.execution_bridge.bridge as mod

    call_count = itertools.count()

    with patch.object(mod, "subscribe_since", return_value=([], "0")) as mock_sub, \
         patch.object(mod, "publish"):
        from services.execution_bridge.bridge import ExecutionBridge
        bridge = ExecutionBridge(symbol="BTCUSDT", exchange="bitget")

        def stop_after_one(*a, **kw):
            if next(call_count) >= 1:
                raise SystemExit
        with patch("time.sleep", side_effect=stop_after_one):
            try:
                bridge.run()
            except SystemExit:
                pass

    mock_sub.assert_called()
    args = mock_sub.call_args[0]
    assert len(args) == 2, "subscribe_since must be called with (channel, last_id) positionally"
    assert args[1] == "0", "Initial last_id must be '0'"
