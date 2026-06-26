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


def test_context_includes_sentiment_when_available():
    from unittest.mock import patch
    with patch("services.orchestrator.context.get_state") as mock_state, \
         patch("services.orchestrator.context.subscribe_since", return_value=([], "0")):
        mock_state.side_effect = lambda key: (
            {"drawdown_pct": 1.0, "is_stopped": False,
             "exposure_pct": 20.0, "daily_pnl_pct": 0.5, "open_positions": 1}
            if key == "risk:state"
            else {"fear_greed_score": 0.72, "news_sentiment": 0.65}
        )
        from services.orchestrator.context import build_context
        prompt, _, _, _ = build_context()
    assert "Fear & Greed" in prompt
    assert "0.72" in prompt
