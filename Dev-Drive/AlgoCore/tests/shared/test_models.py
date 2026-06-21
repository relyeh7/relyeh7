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
