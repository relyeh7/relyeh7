import time
import numpy as np
from collections import defaultdict
from shared import events
from shared.state import set_state, publish, subscribe_since


class PerformanceTracker:
    def __init__(self):
        self._pnls:   dict[str, list[float]] = defaultdict(list)
        self._equity: dict[str, float]       = defaultdict(lambda: 10_000.0)
        self._max_eq: dict[str, float]       = defaultdict(lambda: 10_000.0)
        self._max_dd: dict[str, float]       = defaultdict(float)

    def on_trade(self, trade: dict) -> dict:
        strat = trade.get("strategy", "unknown")
        pnl   = float(trade.get("pnl", 0.0))
        self._pnls[strat].append(pnl)

        self._equity[strat] += pnl
        eq = self._equity[strat]
        if eq > self._max_eq[strat]:
            self._max_eq[strat] = eq
        dd = (1.0 - eq / self._max_eq[strat]) * 100.0
        if dd > self._max_dd[strat]:
            self._max_dd[strat] = dd

        stats = self.get_stats(strat)
        set_state(f"perf:{strat}", stats)
        publish(events.PERF_UPDATE, stats)
        return stats

    def get_stats(self, strategy: str) -> dict:
        pnls = self._pnls.get(strategy, [])
        n    = len(pnls)
        if n == 0:
            return {"strategy": strategy, "n_trades": 0, "win_rate": 0.0,
                    "sharpe": 0.0, "max_dd": 0.0, "total_pnl": 0.0}
        arr     = np.array(pnls, dtype=float)
        wins    = float(np.sum(arr > 0))
        sharpe  = (float(np.mean(arr)) / float(np.std(arr)) * np.sqrt(252 * 96)
                   if n >= 2 and float(np.std(arr)) > 0 else 0.0)
        return {
            "strategy":  strategy,
            "n_trades":  n,
            "win_rate":  round(wins / n, 4),
            "sharpe":    round(sharpe, 4),
            "max_dd":    round(self._max_dd.get(strategy, 0.0), 4),
            "total_pnl": round(float(np.sum(arr)), 6),
        }

    def run(self) -> None:
        last_id = "0"
        while True:
            trades, last_id = subscribe_since(events.TRADE_CLOSED, last_id)
            for t in trades:
                self.on_trade(t)
            time.sleep(1)


if __name__ == "__main__":
    PerformanceTracker().run()
