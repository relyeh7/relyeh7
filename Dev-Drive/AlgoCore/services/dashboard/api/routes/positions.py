from fastapi import APIRouter
from shared.state import get_state

router = APIRouter()


@router.get("/positions")
def get_positions():
    return get_state("positions") or {}
