from unittest.mock import patch, MagicMock


def test_telegram_client_send_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    with patch("services.notifications.telegram.requests.post", return_value=mock_resp):
        from services.notifications.telegram import TelegramClient
        client = TelegramClient("bot123", "chat456")
        result = client.send("Hello AlgoCore!")
    assert result is True


def test_telegram_client_send_failure_returns_false():
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}
    with patch("services.notifications.telegram.requests.post", return_value=mock_resp):
        from services.notifications.telegram import TelegramClient
        client = TelegramClient("bad-token", "chat")
        result = client.send("test")
    assert result is False


def test_telegram_client_send_exception_returns_false():
    with patch("services.notifications.telegram.requests.post", side_effect=Exception("network")):
        from services.notifications.telegram import TelegramClient
        client = TelegramClient("t", "c")
        result = client.send("test")
    assert result is False


def test_alert_subscriber_sends_on_risk_alert():
    risk_payload = {"level": "STOP", "drawdown_pct": 7.0}

    call_count = [0]

    def fake_subscribe(channel, last_id="0"):
        call_count[0] += 1
        if call_count[0] == 1 and channel == "risk:alert":
            return [risk_payload], "1-0"
        return [], last_id

    mock_client = MagicMock()
    mock_client.send.return_value = True

    with patch("services.notifications.alerts.subscribe_since", side_effect=fake_subscribe), \
         patch("services.notifications.alerts.time.sleep"):
        from services.notifications.alerts import AlertSubscriber
        sub = AlertSubscriber(mock_client, max_iterations=1)
        sub.listen()

    assert mock_client.send.called
    sent_msg = mock_client.send.call_args[0][0]
    assert "STOP" in sent_msg or "risk" in sent_msg.lower()


def test_telegram_client_no_args_reads_from_settings():
    """TelegramClient() with no args must read token/chat_id from settings."""
    import services.notifications.telegram as tg_mod

    with patch.object(tg_mod, "settings") as mock_s:
        mock_s.telegram_bot_token = "settings-token"
        mock_s.telegram_chat_id   = "settings-chat"
        client = tg_mod.TelegramClient()

    assert client._token   == "settings-token"
    assert client._chat_id == "settings-chat"


def test_telegram_client_explicit_args_override_settings():
    """Explicit token/chat_id must override settings values."""
    from services.notifications.telegram import TelegramClient
    client = TelegramClient("explicit-token", "explicit-chat")
    assert client._token   == "explicit-token"
    assert client._chat_id == "explicit-chat"


def test_alert_subscriber_default_client_does_not_raise():
    """AlertSubscriber() without explicit client must not raise TypeError."""
    import services.notifications.telegram as tg_mod

    with patch.object(tg_mod, "settings") as mock_s:
        mock_s.telegram_bot_token = ""
        mock_s.telegram_chat_id   = ""
        from services.notifications.alerts import AlertSubscriber
        try:
            sub = AlertSubscriber()
        except TypeError as exc:
            raise AssertionError(
                f"AlertSubscriber() must not raise TypeError, got: {exc}"
            ) from exc
    assert sub._tg is not None
