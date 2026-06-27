def test_rules_stop_all_on_drawdown():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 7.0, "is_stopped": True, "exposure_pct": 50.0}
    decision = apply_rules(risk, [])
    assert decision["action"] == "STOP_ALL"


def test_rules_pause_on_high_drawdown():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 4.5, "is_stopped": False, "exposure_pct": 50.0}
    decision = apply_rules(risk, [])
    assert decision["action"] == "PAUSE_STRATEGY"


def test_rules_hold_on_normal_conditions():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 1.0, "is_stopped": False, "exposure_pct": 30.0}
    decision = apply_rules(risk, [])
    assert decision["action"] == "HOLD"


def test_rules_buy_on_high_confidence_ml_signal():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 0.5, "is_stopped": False, "exposure_pct": 20.0}
    signals = [{"action": "BUY", "confidence": 0.85, "symbol": "ETHUSDT"}]
    decision = apply_rules(risk, signals)
    assert decision["action"] == "BUY"


def test_rules_stop_all_on_daily_loss():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 1.0, "is_stopped": False,
            "exposure_pct": 20.0, "daily_pnl_pct": -5.5}
    decision = apply_rules(risk, [])
    assert decision["action"] == "STOP_ALL"
    assert "daily" in decision["reason"].lower() or "loss" in decision["reason"].lower()


def test_rules_respects_stop_on_drawdown_pct_from_settings():
    """apply_rules stop threshold must come from settings, not a hardcoded literal."""
    from services.orchestrator.rules import apply_rules
    from unittest.mock import patch

    with patch("services.orchestrator.rules.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 3.0
        mock_s.daily_loss_limit_pct = 5.0
        risk = {"drawdown_pct": 3.5, "is_stopped": False,
                "exposure_pct": 10.0, "daily_pnl_pct": 0.0}
        decision = apply_rules(risk, [])

    assert decision["action"] == "STOP_ALL", (
        "drawdown_pct=3.5 must trigger STOP_ALL when stop_on_drawdown_pct=3.0 via settings"
    )
