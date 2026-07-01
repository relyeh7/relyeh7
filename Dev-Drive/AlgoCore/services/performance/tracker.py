import signal
import sys
import time
import numpy as np
from collections import defaultdict
from shared import events
from shared.health import start_health_server
from shared.state import get_state, set_state, publish, subscribe_since

_SNAPSHOT_KEY = "perf:snapshot"


class PerformanceTracker:
    def __init__(self):
        self._pnls:   dict[str, list[float]] = defaultdict(list)
        self._equity: dict[str, float]       = defaultdict(lambda: 10_000.0)
        self._max_eq: dict[str, float]       = defaultdict(lambda: 10_000.0)
        self._max_dd: dict[str, float]       = defaultdict(float)
        self._load_snapshot()

    def _load_snapshot(self) -> None:
        snap = get_state(_SNAPSHOT_KEY)
        if not snap:
            return
        for strat, data in snap.items():
            self._pnls[strat]   = data.get("pnls", [])
            self._equity[strat] = float(data.get("equity", 10_000.0))
            self._max_eq[strat] = float(data.get("max_eq", 10_000.0))
            self._max_dd[strat] = float(data.get("max_dd", 0.0))

    def _save_snapshot(self) -> None:
        snap = {
            strat: {
                "pnls":   self._pnls[strat],
                "equity": self._equity[strat],
                "max_eq": self._max_eq[strat],
                "max_dd": self._max_dd[strat],
            }
            for strat in self._pnls
        }
        set_state(_SNAPSHOT_KEY, snap)

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
        self._save_snapshot()
        return stats

    def get_stats(self, strategy: str) -> dict:
        pnls = self._pnls.get(strategy, [])
        n    = len(pnls)
        if n == 0:
            return {"strategy": strategy, "n_trades": 0, "win_rate": 0.0,
                    "sharpe": 0.0, "max_dd": 0.0, "total_pnl": 0.0,
                    "profit_factor": 0.0}
        arr          = np.array(pnls, dtype=float)
        wins         = float(np.sum(arr > 0))
        total_wins   = float(np.sum(arr[arr > 0])) if wins > 0 else 0.0
        total_losses = float(np.abs(np.sum(arr[arr < 0]))) if (n - wins) > 0 else 0.0
        profit_factor = round(total_wins / total_losses, 4) if total_losses > 0 else 0.0
        sharpe        = (float(np.mean(arr)) / float(np.std(arr)) * np.sqrt(252 * 96)
                         if n >= 2 and float(np.std(arr)) > 0 else 0.0)
        return {
            "strategy":      strategy,
            "n_trades":      n,
            "win_rate":      round(wins / n, 4),
            "sharpe":        round(sharpe, 4),
            "max_dd":        round(self._max_dd.get(strategy, 0.0), 4),
            "total_pnl":     round(float(np.sum(arr)), 6),
            "profit_factor": profit_factor,
        }

    def _register_shutdown(self) -> None:
        def _handler(signum, frame):
            self._save_snapshot()
            sys.exit(0)
        signal.signal(signal.SIGTERM, _handler)

    def run(self) -> None:
        self._register_shutdown()
        start_health_server(8083)
        last_id = "0"
        while True:
            trades, last_id = subscribe_since(events.TRADE_CLOSED, last_id)
            for t in trades:
                self.on_trade(t)
            time.sleep(1)


if __name__ == "__main__":
    PerformanceTracker().run()
