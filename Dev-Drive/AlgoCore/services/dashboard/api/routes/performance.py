from fastapi import APIRouter
from shared.state import get_state

router = APIRouter()


@router.get("/performance/{strategy}")
def get_performance(strategy: str):
    return get_state(f"perf:{strategy}") or {}
