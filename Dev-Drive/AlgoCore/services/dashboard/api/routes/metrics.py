from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from shared.state import get_state

router = APIRouter()

_METRIC_META = [
    ("algocore_drawdown_pct",     "gauge",   "Current portfolio drawdown as a percentage."),
    ("algocore_daily_pnl_pct",    "gauge",   "Daily profit and loss as a percentage."),
    ("algocore_positions_open",   "gauge",   "Number of currently open positions."),
    ("algocore_exposure_pct",     "gauge",   "Current capital exposure as a percentage."),
    ("algocore_is_stopped",       "gauge",   "1 if the trading system is stopped, 0 otherwise."),
    ("algocore_ml_trades_total",  "counter", "Total number of ML strategy trades executed."),
    ("algocore_ml_win_rate",      "gauge",   "ML strategy win rate (0.0-1.0)."),
    ("algocore_ml_total_pnl",     "gauge",   "ML strategy cumulative profit and loss."),
    ("algocore_rl_trades_total",  "counter", "Total number of RL strategy trades executed."),
    ("algocore_rl_win_rate",      "gauge",   "RL strategy win rate (0.0-1.0)."),
    ("algocore_rl_total_pnl",     "gauge",   "RL strategy cumulative profit and loss."),
]


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics() -> str:
    risk    = get_state("risk:state") or {}
    perf_ml = get_state("perf:ml") or {}
    perf_rl = get_state("perf:rl") or {}

    values = [
        risk.get("drawdown_pct", 0.0),
        risk.get("daily_pnl_pct", 0.0),
        risk.get("open_positions", 0),
        risk.get("exposure_pct", 0.0),
        1 if risk.get("is_stopped", False) else 0,
        perf_ml.get("n_trades", 0),
        perf_ml.get("win_rate", 0.0),
        perf_ml.get("total_pnl", 0.0),
        perf_rl.get("n_trades", 0),
        perf_rl.get("win_rate", 0.0),
        perf_rl.get("total_pnl", 0.0),
    ]

    lines: list[str] = []
    for (name, metric_type, help_text), value in zip(_METRIC_META, values):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")
        lines.append(f"{name} {value}")

    return "\n".join(lines)
