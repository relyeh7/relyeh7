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
