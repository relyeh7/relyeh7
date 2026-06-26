from unittest.mock import patch


def test_build_context_reads_risk_state_key():
    """Ensure build_context reads 'risk:state' not 'risk'."""
    import services.orchestrator.context as mod

    captured_keys = []

    def mock_get_state(key):
        captured_keys.append(key)
        return None

    with patch.object(mod, "get_state", side_effect=mock_get_state), \
         patch.object(mod, "subscribe_since", return_value=([], "0")):
        from services.orchestrator.context import build_context
        build_context("0")

    assert "risk:state" in captured_keys, (
        "build_context must read 'risk:state' (written by RiskService), not 'risk'"
    )
    assert "risk" not in [k for k in captured_keys if k == "risk"], (
        "build_context must not read bare 'risk' key — RiskService writes 'risk:state'"
    )


def test_build_context_returns_four_tuple():
    """Ensure build_context returns (prompt, risk, signals, last_signal_id)."""
    import services.orchestrator.context as mod

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "subscribe_since", return_value=([], "abc-123")):
        from services.orchestrator.context import build_context
        result = build_context("0")

    assert isinstance(result, tuple), "build_context must return a tuple"
    assert len(result) == 4, "build_context must return 4-tuple: (prompt, risk, signals, last_signal_id)"
    prompt, risk, signals, last_signal_id = result
    assert isinstance(prompt, str)
    assert isinstance(risk, dict)
    assert isinstance(signals, list)
    assert last_signal_id == "abc-123", "Returned last_signal_id must match subscribe_since output"


def test_build_context_reads_price_from_state_not_stream():
    """Ensure build_context does NOT subscribe to PRICE_TICK stream; reads price:{symbol} state."""
    import services.orchestrator.context as mod
    from shared import events

    subscribe_channels = []

    def mock_subscribe_since(channel, last_id="0"):
        subscribe_channels.append(channel)
        return [], last_id

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "subscribe_since", side_effect=mock_subscribe_since):
        from services.orchestrator.context import build_context
        build_context("0")

    assert events.PRICE_TICK not in subscribe_channels, (
        "build_context must not subscribe to PRICE_TICK stream — read price:{symbol} state instead"
    )
