import pytest
from core.lab_db import LabDB
import os

def test_db_initialization():
    db_path = "test_stress_lab.db"
    if os.path.exists(db_path): os.remove(db_path)
    db = LabDB(db_path)
    # Check tables exist
    cursor = db.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    assert "experts" in tables
    assert "tasks" in tables
    db.close()
    if os.path.exists(db_path): os.remove(db_path)
