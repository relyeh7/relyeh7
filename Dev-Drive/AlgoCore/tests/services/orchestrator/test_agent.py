from unittest.mock import MagicMock, patch


def test_agent_falls_back_to_rules_when_no_api_keys():
    from services.orchestrator.agent import OrchestratorAgent
    agent = OrchestratorAgent(anthropic_key="", gemini_key="")
    result = agent.decide(
        context="test",
        risk={"drawdown_pct": 1.0, "is_stopped": False, "exposure_pct": 20.0},
        signals=[],
    )
    assert "action" in result
    assert result["action"] in {"HOLD", "BUY", "SELL", "PAUSE_STRATEGY",
                                "RESUME_ALL", "STOP_ALL", "ADJUST_POSITION"}


def test_agent_uses_claude_when_key_available():
    mock_client = MagicMock()
    mock_block  = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "set_trading_action"
    mock_block.input = {"action": "HOLD", "reason": "test", "confidence": 0.8,
                        "market": "crypto", "exchange": "auto", "strategy": "ml",
                        "capital_pct": 0.0}
    mock_client.messages.create.return_value.content = [mock_block]

    with patch("services.orchestrator.agent.Anthropic", return_value=mock_client):
        from services.orchestrator.agent import OrchestratorAgent
        agent = OrchestratorAgent(anthropic_key="sk-test", gemini_key="")
        result = agent.decide(
            context="test",
            risk={"drawdown_pct": 1.0, "is_stopped": False, "exposure_pct": 20.0},
            signals=[],
        )
    assert result["action"] == "HOLD"
    assert result["confidence"] == 0.8
