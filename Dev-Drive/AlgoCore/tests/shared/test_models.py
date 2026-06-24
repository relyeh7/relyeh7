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


def test_trade_model():
    from shared.models import Trade, Side
    from datetime import datetime, timezone
    t = Trade(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=50000.0, exit_price=51000.0,
        size=0.01, pnl=10.0, strategy="ml",
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
    )
    assert t.pnl == 10.0
    assert t.id != ""


def test_position_model():
    from shared.models import Position, Side
    p = Position(symbol="ETHUSDT", side=Side.BUY, entry_price=3000.0, size=0.1, strategy="rl")
    assert p.symbol == "ETHUSDT"
    assert p.entry_price == 3000.0


def test_backtest_result_model():
    from shared.models import BacktestResult
    r = BacktestResult(
        symbol="BTCUSDT", strategy="ml", n_trades=10,
        sharpe=1.5, max_dd=3.2, win_rate=0.6,
        profit_factor=1.8, total_pnl=500.0,
        equity_curve=[10000.0, 10050.0, 10100.0],
    )
    assert r.win_rate == 0.6
    assert len(r.equity_curve) == 3


def test_order_state_model():
    from shared.models import OrderState, Side
    from datetime import datetime, timezone
    o = OrderState(
        id="ord-001", symbol="BTCUSDT", side=Side.BUY,
        price=50000.0, size=0.01, exchange="bitget", strategy="ml",
        placed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert o.id == "ord-001"
    assert o.exchange == "bitget"
    assert o.strategy == "ml"
