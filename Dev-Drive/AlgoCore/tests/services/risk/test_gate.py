from unittest.mock import patch


def test_gate_blocked_when_is_stopped_true():
    risk = {"is_stopped": True, "drawdown_pct": 7.0, "open_positions": 1}
    with patch("services.risk.gate.get_state", return_value=risk):
        from services.risk.gate import RiskGate
        gate = RiskGate()
        assert gate.is_blocked() is True


def test_gate_blocked_when_drawdown_exceeds_threshold():
    risk = {"is_stopped": False, "drawdown_pct": 7.0, "open_positions": 1}
    with patch("services.risk.gate.get_state", return_value=risk), \
         patch("services.risk.gate.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        from services.risk.gate import RiskGate
        gate = RiskGate()
        assert gate.is_blocked() is True


def test_gate_not_blocked_when_risk_normal():
    risk = {"is_stopped": False, "drawdown_pct": 2.0, "open_positions": 1}
    with patch("services.risk.gate.get_state", return_value=risk), \
         patch("services.risk.gate.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        from services.risk.gate import RiskGate
        gate = RiskGate()
        assert gate.is_blocked() is False


def test_gate_not_blocked_when_no_risk_state():
    with patch("services.risk.gate.get_state", return_value=None):
        from services.risk.gate import RiskGate
        gate = RiskGate()
        assert gate.is_blocked() is False
