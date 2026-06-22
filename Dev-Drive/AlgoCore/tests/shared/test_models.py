from datetime import datetime, timezone
from shared.models import PriceTick, Signal, Order, RiskState, Exchange, Side


def test_price_tick_validation():
    tick = PriceTick(
        symbol="ETHUSDT",
        price=2500.0,
        volume=1000.0,
        timestamp=datetime.now(timezone.utc),
        exchange=Exchange.BITGET,
    )
    assert tick.price == 2500.0
    assert tick.exchange == Exchange.BITGET


def test_signal_action_must_be_valid():
    sig = Signal(
        symbol="BTCUSDT",
        action="BUY",
        confidence=0.85,
        strategy="ml_xgboost",
        exchange=Exchange.BINANCE,
        timestamp=datetime.now(timezone.utc),
    )
    assert sig.confidence == 0.85


def test_risk_state_defaults():
    state = RiskState(total_equity=1000.0)
    assert state.daily_pnl == 0.0
    assert state.is_stopped is False
    assert state.drawdown_pct == 0.0


def test_order_roundtrip():
    order = Order(
        order_id="abc-123",
        symbol="ETHUSDT",
        side=Side.BUY,
        price=2490.0,
        size=0.01,
        exchange=Exchange.BITGET,
        status="open",
        timestamp=datetime.now(timezone.utc),
    )
    dumped = order.model_dump()
    restored = Order.model_validate(dumped)
    assert restored.order_id == "abc-123"


def test_ohlcv_bar():
    from shared.models import OHLCVBar
    bar = OHLCVBar(timestamp="2026-01-01T00:00:00", open=100.0, high=105.0,
                   low=99.0, close=103.0, volume=1500.0)
    assert bar.close == 103.0
    d = bar.model_dump()
    assert d["volume"] == 1500.0


def test_orchestrator_decision_defaults():
    from shared.models import OrchestratorDecision
    dec = OrchestratorDecision(action="HOLD", reason="calm market", confidence=0.7)
    assert dec.market == "crypto"
    assert dec.capital_pct == 0.0
    assert dec.exchange == "auto"


def test_sentiment_state_model():
    from shared.models import SentimentState
    s = SentimentState(fear_greed_score=0.72, news_sentiment=0.6, updated_at="2026-06-21T10:00:00Z")
    assert s.fear_greed_score == 0.72
    assert s.news_sentiment == 0.6
    assert 0.0 <= s.fear_greed_score <= 1.0
    assert 0.0 <= s.news_sentiment <= 1.0
