from unittest.mock import patch


def test_paper_engine_fill_publishes_order_filled():
    with patch("services.paper.engine.publish") as mock_pub:
        from services.paper.engine import PaperEngine
        engine = PaperEngine(slippage_pct=0.001)
        decision = {"symbol": "BTCUSDT", "action": "BUY", "size": "0.01", "strategy": "ml"}
        fill = engine.fill(decision, current_price=50000.0)
    assert fill["symbol"] == "BTCUSDT"
    assert fill["side"] == "buy"
    assert fill["price"] > 50000.0  # slippage applied
    assert fill["size"] == 0.01
    assert "order_id" in fill
    mock_pub.assert_called()


def test_paper_engine_sell_price_below_market():
    with patch("services.paper.engine.publish"):
        from services.paper.engine import PaperEngine
        engine = PaperEngine(slippage_pct=0.001)
        decision = {"symbol": "BTCUSDT", "action": "SELL", "size": "0.01", "strategy": "ml"}
        fill = engine.fill(decision, current_price=50000.0)
    assert fill["price"] < 50000.0  # sell fills below market


def test_paper_engine_run_once_returns_none_without_price():
    with patch("services.paper.engine.get_state", return_value=None), \
         patch("services.paper.engine.publish"):
        from services.paper.engine import PaperEngine
        engine = PaperEngine()
        result = engine.run_once({"symbol": "BTCUSDT", "action": "BUY", "size": "0.01"})
    assert result is None


def test_paper_engine_run_once_fills_when_price_available():
    with patch("services.paper.engine.get_state", return_value={"price": 48000.0}), \
         patch("services.paper.engine.publish"):
        from services.paper.engine import PaperEngine
        engine = PaperEngine()
        result = engine.run_once({"symbol": "BTCUSDT", "action": "BUY", "size": "0.01", "strategy": "test"})
    assert result is not None
    assert result["price"] > 48000.0
