"""Phase 17 smoke tests — Open Position Recovery + .env Completeness."""
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone


# ── T1: TradeJournal positions table ─────────────────────────────────────────

def test_trade_journal_has_ensure_positions_table():
    """TradeJournal must expose ensure_positions_table(), save_position(),
    delete_position(), and get_open_positions()."""
    from services.journal.trade_journal import TradeJournal
    for method in ("ensure_positions_table", "save_position", "delete_position", "get_open_positions"):
        assert hasattr(TradeJournal, method), f"TradeJournal missing method: {method}"


def test_trade_journal_save_position_calls_upsert():
    """save_position() must execute the upsert SQL with correct column values."""
    from services.journal.trade_journal import TradeJournal
    from shared.models import Position, Side

    pos = Position(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=50_000.0, size=0.01,
        strategy="ml",
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    mock_conn  = MagicMock()
    mock_cur   = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__  = MagicMock(return_value=False)
    mock_cur.__enter__  = lambda s: s
    mock_cur.__exit__   = MagicMock(return_value=False)
    mock_conn.cursor    = MagicMock(return_value=mock_cur)

    with patch("services.journal.trade_journal.psycopg2.connect", return_value=mock_conn):
        journal = TradeJournal("postgresql://test")
        journal.save_position("BTCUSDT", pos)

    mock_cur.execute.assert_called_once()
    args = mock_cur.execute.call_args[0][1]
    assert args[0] == "BTCUSDT"
    assert args[1] == "buy"
    assert args[2] == 50_000.0


def test_trade_journal_delete_position_calls_delete():
    """delete_position() must execute DELETE SQL for the given symbol."""
    from services.journal.trade_journal import TradeJournal

    mock_conn = MagicMock()
    mock_cur  = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__  = MagicMock(return_value=False)
    mock_cur.__enter__  = lambda s: s
    mock_cur.__exit__   = MagicMock(return_value=False)
    mock_conn.cursor    = MagicMock(return_value=mock_cur)

    with patch("services.journal.trade_journal.psycopg2.connect", return_value=mock_conn):
        journal = TradeJournal("postgresql://test")
        journal.delete_position("BTCUSDT")

    mock_cur.execute.assert_called_once()
    assert mock_cur.execute.call_args[0][1] == ("BTCUSDT",)


# ── T2: PositionManager recovery ─────────────────────────────────────────────

def test_position_manager_recovers_from_postgres_on_redis_miss():
    """When Redis returns None, PositionManager must load positions from PostgreSQL."""
    from services.positions.manager import PositionManager
    from shared.models import Position, Side

    pg_pos = Position(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=50_000.0, size=0.01,
        strategy="ml",
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    mock_journal = MagicMock()
    mock_journal.get_open_positions.return_value = [("BTCUSDT", pg_pos)]

    with patch("services.positions.manager.get_state", return_value=None), \
         patch("services.positions.manager.set_state"), \
         patch("services.positions.manager.publish"):
        mgr = PositionManager(mock_journal)

    assert "BTCUSDT" in mgr._positions
    assert mgr._positions["BTCUSDT"].entry_price == 50_000.0
    mock_journal.get_open_positions.assert_called_once()


def test_position_manager_writes_to_postgres_on_buy_fill():
    """on_fill() with side='buy' must call journal.save_position()."""
    from services.positions.manager import PositionManager

    mock_journal = MagicMock()
    mock_journal.get_open_positions.return_value = []

    with patch("services.positions.manager.get_state", return_value={}), \
         patch("services.positions.manager.set_state"), \
         patch("services.positions.manager.publish"):
        mgr = PositionManager(mock_journal)
        mgr.on_fill({"symbol": "BTCUSDT", "side": "buy", "price": "50000", "size": "0.01", "strategy": "ml"})

    mock_journal.save_position.assert_called_once()
    symbol_arg = mock_journal.save_position.call_args[0][0]
    assert symbol_arg == "BTCUSDT"


def test_position_manager_deletes_from_postgres_on_sell_fill():
    """on_fill() with side='sell' must call journal.delete_position() after closing."""
    from services.positions.manager import PositionManager
    from shared.models import Position, Side

    existing_pos = Position(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=50_000.0, size=0.01,
        strategy="ml",
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    mock_journal = MagicMock()
    mock_journal.get_open_positions.return_value = []

    with patch("services.positions.manager.get_state", return_value={}), \
         patch("services.positions.manager.set_state"), \
         patch("services.positions.manager.publish"):
        mgr = PositionManager(mock_journal)
        mgr._positions["BTCUSDT"] = existing_pos
        mgr.on_fill({"symbol": "BTCUSDT", "side": "sell", "price": "51000", "size": "0.01", "strategy": "ml"})

    mock_journal.delete_position.assert_called_once_with("BTCUSDT")


# ── T3: .env.example completeness ────────────────────────────────────────────

def test_env_example_covers_all_settings_fields():
    """Every field in shared.config.Settings must appear in .env.example."""
    from shared.config import Settings

    with open(".env.example") as fh:
        env_text = fh.read().upper()

    missing = []
    for field_name in Settings.model_fields:
        if field_name.upper() not in env_text:
            missing.append(field_name)

    assert not missing, f".env.example is missing documentation for: {missing}"
