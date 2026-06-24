from unittest.mock import MagicMock, patch


def _trade_payload(pnl: float = 10.5, side: str = "buy") -> dict:
    return {"symbol": "BTCUSDT", "side": side, "pnl": pnl,
            "strategy": "ml", "closed_at": "2026-01-01T10:00:00+00:00"}


def _risk_payload() -> dict:
    return {"drawdown_pct": 4.5, "action": "PAUSE_STRATEGY"}


def test_on_trade_closed_sends_telegram():
    mock_tg = MagicMock()
    with patch("services.notifications.alerts.get_state", return_value=None):
        from services.notifications.alerts import AlertSubscriber
        sub = AlertSubscriber(client=mock_tg)
        sub.on_trade_closed(_trade_payload(10.5))
    mock_tg.send.assert_called_once()
    msg = mock_tg.send.call_args[0][0]
    assert "BTCUSDT" in msg
    assert "10.5" in msg or "+10.5" in msg


def test_on_risk_alert_sends_telegram():
    mock_tg = MagicMock()
    from services.notifications.alerts import AlertSubscriber
    sub = AlertSubscriber(client=mock_tg)
    sub.on_risk_alert(_risk_payload())
    mock_tg.send.assert_called_once()
    msg = mock_tg.send.call_args[0][0]
    assert "4.5" in msg


def test_daily_summary_sent_once_per_day():
    mock_tg = MagicMock()
    perf = {"n_trades": 5, "total_pnl": 25.0, "win_rate": 0.6}
    with patch("services.notifications.alerts.get_state", return_value=perf):
        from services.notifications.alerts import AlertSubscriber
        sub = AlertSubscriber(client=mock_tg)
        sub._last_summary_date = None  # force summary on first call
        sub._send_daily_summary()
        sub._send_daily_summary()  # second call same day — should not send again
    assert mock_tg.send.call_count == 1
