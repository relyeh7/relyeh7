from fastapi import APIRouter, Query
from shared.config import settings
from services.journal.trade_journal import TradeJournal

router = APIRouter()


@router.get("/trades")
def get_trades(limit: int = Query(default=50, le=500)):
    try:
        journal = TradeJournal(settings.postgres_url)
        trades = journal.get_recent(limit=limit)
        return [t.model_dump(mode="json") for t in trades]
    except Exception:
        return []
