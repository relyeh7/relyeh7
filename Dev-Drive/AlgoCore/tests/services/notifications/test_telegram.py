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
