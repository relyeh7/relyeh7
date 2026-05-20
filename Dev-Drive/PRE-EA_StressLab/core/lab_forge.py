import logging
from core.data_forge import DataForge

logger = logging.getLogger(__name__)

class LabForge:
    def __init__(self, db, data_forge=None):
        self.db = db
        self.data_forge = data_forge or DataForge(init_mt5=False)
