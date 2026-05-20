import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LabDB:
    """
    Centralized SQLite database manager for the PRE-EA Stress Lab.
    Supports context management, concurrency, and dictionary-like data access.
    """
    def __init__(self, db_path="stress_lab.db"):
        self.db_path = db_path
        self.conn = None
        try:
            self.conn = sqlite3.connect(db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            logger.info(f"Database initialized at {db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _create_tables(self):
        """Creates the necessary tables if they don't exist."""
        try:
            cursor = self.conn.cursor()
            # Experts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    name TEXT,
                    has_set BOOLEAN,
                    last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expert_id INTEGER NOT NULL,
                    scenario TEXT,
                    symbol TEXT,
                    status TEXT DEFAULT 'PENDING',
                    report_path TEXT,
                    error_msg TEXT,
                    profit_factor REAL,
                    max_drawdown REAL,
                    recovery_factor REAL,
                    resilience_score REAL,
                    FOREIGN KEY(expert_id) REFERENCES experts(id)
                )
            """)
            self.conn.commit()
            logger.debug("Tables created or already exist.")
        except sqlite3.Error as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            logger.info(f"Database connection closed for {self.db_path}")
            self.conn = None
