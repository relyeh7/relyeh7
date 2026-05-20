import sqlite3

class LabDB:
    def __init__(self, db_path="stress_lab.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                name TEXT,
                has_set BOOLEAN,
                last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expert_id INTEGER,
                scenario TEXT,
                symbol TEXT,
                status TEXT DEFAULT 'PENDING',
                report_path TEXT,
                error_msg TEXT,
                FOREIGN KEY(expert_id) REFERENCES experts(id)
            )
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()
