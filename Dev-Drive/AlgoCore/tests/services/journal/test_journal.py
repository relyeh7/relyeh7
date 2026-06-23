from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone


def _make_trade(pnl: float = 10.0):
    from shared.models import Trade, Side
    return Trade(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=50000.0, exit_price=51000.0,
        size=0.01, pnl=pnl, strategy="ml",
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
    )


def test_journal_ensure_table_creates_schema():
    mock_conn = MagicMock()
    mock_cur  = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__  = MagicMock(return_value=False)

    with patch("services.journal.trade_journal.psycopg2.connect", return_value=mock_conn):
        from services.journal.trade_journal import TradeJournal
        j = TradeJournal("postgresql://x")
        j.ensure_table()

    mock_cur.execute.assert_called_once()
    sql = mock_cur.execute.call_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS trades" in sql


def test_journal_save_inserts_row():
    mock_conn = MagicMock()
    mock_cur  = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__  = MagicMock(return_value=False)
    trade = _make_trade(pnl=25.0)

    with patch("services.journal.trade_journal.psycopg2.connect", return_value=mock_conn):
        from services.journal.trade_journal import TradeJournal
        j = TradeJournal("postgresql://x")
        j.save(trade)

    mock_cur.execute.assert_called_once()
    sql, params = mock_cur.execute.call_args[0]
    assert "INSERT INTO trades" in sql
    assert trade.id in params


def test_journal_get_recent_returns_trades():
    mock_conn = MagicMock()
    mock_cur  = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__  = MagicMock(return_value=False)
    trade = _make_trade()
    mock_cur.fetchall.return_value = [(
        trade.id, trade.symbol, trade.side.value,
        trade.entry_price, trade.exit_price, trade.size,
        trade.pnl, trade.strategy,
        trade.opened_at.isoformat(), trade.closed_at.isoformat(),
    )]

    with patch("services.journal.trade_journal.psycopg2.connect", return_value=mock_conn):
        from services.journal.trade_journal import TradeJournal
        j = TradeJournal("postgresql://x")
        results = j.get_recent(limit=10)

    assert len(results) == 1
    assert results[0].symbol == "BTCUSDT"
    assert results[0].pnl == trade.pnl
