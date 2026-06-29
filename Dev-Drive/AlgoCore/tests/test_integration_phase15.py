from unittest.mock import patch
import services.notifications.telegram as tg_mod
import shared.state as state_mod
import services.dashboard.api.main as main_mod


def test_telegram_client_no_args_does_not_raise():
    """TelegramClient() with no args must not raise TypeError — Phase 15."""
    with patch.object(tg_mod, "settings") as mock_s:
        mock_s.telegram_bot_token = "test-token"
        mock_s.telegram_chat_id   = "test-chat"
        from services.notifications.telegram import TelegramClient
        client = TelegramClient()
    assert client._token   == "test-token"
    assert client._chat_id == "test-chat"


def test_alert_subscriber_instantiates_without_client():
    """AlertSubscriber() with no client arg must instantiate cleanly — Phase 15."""
    with patch.object(tg_mod, "settings") as mock_s:
        mock_s.telegram_bot_token = ""
        mock_s.telegram_chat_id   = ""
        from services.notifications.alerts import AlertSubscriber
        sub = AlertSubscriber()
    assert hasattr(sub, "_tg"), "AlertSubscriber must have _tg attribute"
    assert hasattr(sub, "_last_id_risk")
    assert hasattr(sub, "_last_id_trade")


def test_health_redis_down_still_returns_200():
    """GET /health must return 200 with redis='down' when Redis unavailable — Phase 15."""
    from fastapi.testclient import TestClient

    with patch.object(state_mod, "_redis") as mock_redis:
        mock_redis.ping.side_effect = Exception("timeout")
        client = TestClient(main_mod.app)
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["redis"] == "down"
    assert resp.json()["status"] == "ok"
