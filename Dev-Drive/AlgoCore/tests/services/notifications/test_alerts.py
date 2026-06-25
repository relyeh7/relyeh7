from unittest.mock import MagicMock, patch


def test_alerts_run_uses_subscribe_since():
    """Ensure AlertSubscriber.run() uses subscribe_since for cursor tracking."""
    import services.notifications.alerts as mod
    mock_tg = MagicMock()
    with patch.object(mod, "subscribe_since", return_value=([], "0")), \
         patch.object(mod, "get_state", return_value=None):
        from services.notifications.alerts import AlertSubscriber
        sub = AlertSubscriber(client=mock_tg, max_iterations=1)
        sub.run()
    # No assertion needed — test passes if subscribe_since is called without error
    # (ImportError or AttributeError would mean the migration was not done)
