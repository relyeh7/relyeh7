import logging

from shared.config import settings
from shared.state import get_state

logger = logging.getLogger(__name__)

_MIN_TRADES = 10


class KellySizer:
    def __init__(self, min_size: float = 0.001, max_fraction: float | None = None):
        self._min   = min_size
        self._max_f = max_fraction  # None → use settings.kelly_fraction at call time

    def compute(self, strategy: str) -> float:
        perf = get_state(f"perf:{strategy}")
        if not perf:
            return self._min

        n_trades = int(perf.get("n_trades", 0))
        if n_trades < _MIN_TRADES:
            return self._min

        win_rate = float(perf.get("win_rate", 0.0))
        profit_factor = float(
            perf.get("profit_factor", win_rate / max(1 - win_rate, 1e-10))
        )

        if profit_factor <= 1.0:
            return self._min

        kelly = (win_rate * (profit_factor - 1) - (1 - win_rate)) / max(profit_factor - 1, 1e-10)

        if kelly <= 0:
            return self._min

        cap  = self._max_f if self._max_f is not None else settings.kelly_fraction
        size = min(kelly, cap)
        logger.debug(f"[Kelly] strategy={strategy} kelly={kelly:.4f} capped={size:.4f}")
        return max(size, self._min)
