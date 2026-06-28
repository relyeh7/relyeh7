from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from shared.state import get_state

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics() -> str:
    risk    = get_state("risk:state") or {}
    perf_ml = get_state("perf:ml") or {}
    perf_rl = get_state("perf:rl") or {}
    lines = [
        f'algocore_drawdown_pct {risk.get("drawdown_pct", 0.0)}',
        f'algocore_daily_pnl_pct {risk.get("daily_pnl_pct", 0.0)}',
        f'algocore_positions_open {risk.get("open_positions", 0)}',
        f'algocore_exposure_pct {risk.get("exposure_pct", 0.0)}',
        f'algocore_is_stopped {1 if risk.get("is_stopped", False) else 0}',
        f'algocore_ml_trades_total {perf_ml.get("n_trades", 0)}',
        f'algocore_ml_win_rate {perf_ml.get("win_rate", 0.0)}',
        f'algocore_ml_total_pnl {perf_ml.get("total_pnl", 0.0)}',
        f'algocore_rl_trades_total {perf_rl.get("n_trades", 0)}',
        f'algocore_rl_win_rate {perf_rl.get("win_rate", 0.0)}',
        f'algocore_rl_total_pnl {perf_rl.get("total_pnl", 0.0)}',
    ]
    return "\n".join(lines)
