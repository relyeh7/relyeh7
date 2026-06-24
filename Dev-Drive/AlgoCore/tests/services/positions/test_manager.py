from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


def _make_fill(side: str = "buy", price: float = 50000.0, size: float = 0.01,
               symbol: str = "BTCUSDT", strategy: str = "ml") -> dict:
    return {
        "symbol": symbol, "side": side, "price": price,
        "size": size, "strategy": strategy,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def test_buy_fill_opens_position():
    mock_journal = MagicMock()
    with patch("services.positions.manager.get_state", return_value=None), \
         patch("services.positions.manager.set_state"), \
         patch("services.positions.manager.publish"):
        from services.positions.manager import PositionManager
        pm = PositionManager(mock_journal)
        result = pm.on_fill(_make_fill("buy", 50000.0))
    assert result is None  # no trade closed
    positions = pm.get_positions()
    assert "BTCUSDT" in positions
    assert positions["BTCUSDT"].entry_price == 50000.0


def test_sell_fill_closes_position_and_saves_trade():
    mock_journal = MagicMock()
    with patch("services.positions.manager.get_state", return_value=None), \
         patch("services.positions.manager.set_state"), \
         patch("services.positions.manager.publish"):
        from services.positions.manager import PositionManager
        pm = PositionManager(mock_journal)
        pm.on_fill(_make_fill("buy", 50000.0))
        trade = pm.on_fill(_make_fill("sell", 51000.0))
    assert trade is not None
    assert trade.pnl > 0
    assert trade.entry_price == 50000.0
    assert trade.exit_price == 51000.0
    mock_journal.save.assert_called_once()


def test_sell_without_position_is_noop():
    mock_journal = MagicMock()
    with patch("services.positions.manager.get_state", return_value=None), \
         patch("services.positions.manager.set_state"), \
         patch("services.positions.manager.publish"):
        from services.positions.manager import PositionManager
        pm = PositionManager(mock_journal)
        result = pm.on_fill(_make_fill("sell", 50000.0))
    assert result is None
    mock_journal.save.assert_not_called()
