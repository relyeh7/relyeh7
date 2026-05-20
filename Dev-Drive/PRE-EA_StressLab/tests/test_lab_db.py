import pytest
import sqlite3
import os
from core.lab_db import LabDB

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_lab.db")

def test_lab_db_initialization(db_path):
    """Test that LabDB initializes and creates tables correctly."""
    with LabDB(db_path) as db:
        # Check if tables exist
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "experts" in tables
        assert "tasks" in tables

def test_lab_db_experts_schema(db_path):
    """Test that experts table has the correct columns."""
    with LabDB(db_path) as db:
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(experts)")
        columns = {row['name']: row['type'] for row in cursor.fetchall()}
        
        expected_columns = {
            "id": "INTEGER",
            "path": "TEXT",
            "name": "TEXT",
            "has_set": "BOOLEAN",
            "last_scanned": "TIMESTAMP"
        }
        for col, dtype in expected_columns.items():
            assert col in columns
            assert expected_columns[col] in columns[col]

def test_lab_db_tasks_schema(db_path):
    """Test that tasks table has the correct columns."""
    with LabDB(db_path) as db:
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {row['name']: row['type'] for row in cursor.fetchall()}
        
        expected_columns = [
            "id", "expert_id", "scenario", "symbol", "status",
            "report_path", "error_msg", "profit_factor",
            "max_drawdown", "recovery_factor", "resilience_score"
        ]
        for col in expected_columns:
            assert col in columns

def test_lab_db_context_manager(db_path):
    """Test that context manager closes the connection."""
    conn_ref = None
    with LabDB(db_path) as db:
        conn_ref = db.conn
        assert conn_ref is not None
    
    # Connection should be closed. Attempting an operation should raise an error.
    with pytest.raises(sqlite3.ProgrammingError):
        conn_ref.execute("SELECT 1")

def test_lab_db_row_factory(db_path):
    """Test that row_factory is set to sqlite3.Row."""
    with LabDB(db_path) as db:
        db.conn.execute("INSERT INTO experts (path, name) VALUES ('test_path', 'test_name')")
        row = db.conn.execute("SELECT * FROM experts").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row['name'] == 'test_name'
        assert row['path'] == 'test_path'
