import pytest
from unittest.mock import MagicMock
from core.lab_forge import LabForge

def test_lab_forge_init():
    mock_db = MagicMock()
    # We'll mock DataForge inside LabForge or pass it in
    forge = LabForge(db=mock_db)
    assert forge.db == mock_db
    assert forge.data_forge is not None
