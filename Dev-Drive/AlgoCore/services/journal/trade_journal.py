import psycopg2
from datetime import datetime, timezone
from shared.models import Trade, Position, Side

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id          TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price  REAL NOT NULL,
    size        REAL NOT NULL,
    pnl         REAL NOT NULL,
    strategy    TEXT NOT NULL DEFAULT 'unknown',
    opened_at   TEXT NOT NULL,
    closed_at   TEXT NOT NULL
)
"""

_CREATE_POSITIONS_SQL = """
CREATE TABLE IF NOT EXISTS open_positions (
    symbol      TEXT PRIMARY KEY,
    side        TEXT NOT NULL,
    entry_price REAL NOT NULL,
    size        REAL NOT NULL,
    strategy    TEXT NOT NULL DEFAULT 'unknown',
    opened_at   TEXT NOT NULL
)
"""

_INSERT_SQL = """
INSERT INTO trades (id, symbol, side, entry_price, exit_price, size, pnl, strategy, opened_at, closed_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO NOTHING
"""

_SELECT_SQL = "SELECT * FROM trades ORDER BY closed_at DESC LIMIT %s"

_UPSERT_POSITION_SQL = """
INSERT INTO open_positions (symbol, side, entry_price, size, strategy, opened_at)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (symbol) DO UPDATE SET
    side        = EXCLUDED.side,
    entry_price = EXCLUDED.entry_price,
    size        = EXCLUDED.size,
    strategy    = EXCLUDED.strategy,
    opened_at   = EXCLUDED.opened_at
"""

_DELETE_POSITION_SQL  = "DELETE FROM open_positions WHERE symbol = %s"
_SELECT_POSITIONS_SQL = "SELECT symbol, side, entry_price, size, strategy, opened_at FROM open_positions"


class TradeJournal:
    def __init__(self, db_url: str):
        self._db_url = db_url

    def ensure_table(self) -> None:
        conn = psycopg2.connect(self._db_url)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(_CREATE_SQL)
        finally:
            conn.close()

    def ensure_positions_table(self) -> None:
        conn = psycopg2.connect(self._db_url)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(_CREATE_POSITIONS_SQL)
        finally:
            conn.close()

    def save_position(self, symbol: str, position: "Position") -> None:
        conn = psycopg2.connect(self._db_url)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(_UPSERT_POSITION_SQL, (
                    symbol, position.side.value,
                    position.entry_price, position.size,
                    position.strategy, position.opened_at.isoformat(),
                ))
        finally:
            conn.close()

    def delete_position(self, symbol: str) -> None:
        conn = psycopg2.connect(self._db_url)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(_DELETE_POSITION_SQL, (symbol,))
        finally:
            conn.close()

    def get_open_positions(self) -> list[tuple[str, "Position"]]:
        conn = psycopg2.connect(self._db_url)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(_SELECT_POSITIONS_SQL)
                rows = cur.fetchall()
        finally:
            conn.close()
        return [
            (r[0], Position(
                symbol=r[0], side=Side(r[1]),
                entry_price=r[2], size=r[3],
                strategy=r[4],
                opened_at=datetime.fromisoformat(r[5]),
            ))
            for r in rows
        ]

    def save(self, trade: Trade) -> None:
        conn = psycopg2.connect(self._db_url)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(_INSERT_SQL, (
                    trade.id, trade.symbol, trade.side.value,
                    trade.entry_price, trade.exit_price, trade.size,
                    trade.pnl, trade.strategy,
                    trade.opened_at.isoformat(), trade.closed_at.isoformat(),
                ))
        finally:
            conn.close()

    def get_recent(self, limit: int = 100) -> list[Trade]:
        conn = psycopg2.connect(self._db_url)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(_SELECT_SQL, (limit,))
                rows = cur.fetchall()
        finally:
            conn.close()
        return [
            Trade(
                id=r[0], symbol=r[1], side=Side(r[2]),
                entry_price=r[3], exit_price=r[4], size=r[5],
                pnl=r[6], strategy=r[7],
                opened_at=datetime.fromisoformat(r[8]),
                closed_at=datetime.fromisoformat(r[9]),
            )
            for r in rows
        ]
