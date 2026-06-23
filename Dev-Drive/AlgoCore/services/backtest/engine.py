from __future__ import annotations
from typing import Callable
import numpy as np
import pandas as pd

from shared.models import BacktestResult


class BacktestEngine:
    def __init__(self, symbol: str, strategy: str,
                 initial_equity: float = 10_000.0,
                 fee_pct: float = 0.001,
                 position_size: float = 1.0):
        self._symbol   = symbol
        self._strategy = strategy
        self._equity0  = initial_equity
        self._fee      = fee_pct
        self._size     = position_size

    def run(self, df: pd.DataFrame,
            signal_fn: Callable[[pd.Series], str]) -> BacktestResult:
        equity      = self._equity0
        in_position = False
        entry_price = 0.0
        trade_pnls: list[float] = []
        equity_curve: list[float] = [equity] * len(df)

        for pos, (i, row) in enumerate(df.iterrows()):
            sig = signal_fn(row)
            close = float(row["close"])

            if sig == "BUY" and not in_position:
                in_position = True
                entry_price = close

            elif sig == "SELL" and in_position:
                pnl = (close - entry_price) * self._size * (1 - self._fee)
                equity += pnl
                trade_pnls.append(pnl)
                in_position = False

            if in_position:
                unrealized = (close - entry_price) * self._size * (1 - self._fee)
                equity_curve[pos] = equity + unrealized
            else:
                equity_curve[pos] = equity

        # Force-close at end if still in position
        if in_position:
            close = float(df["close"].iloc[-1])
            pnl   = (close - entry_price) * self._size * (1 - self._fee)
            equity += pnl
            trade_pnls.append(pnl)
            equity_curve[-1] = equity

        return self._compute_result(trade_pnls, equity_curve)

    def _compute_result(self, pnls: list[float],
                        equity_curve: list[float]) -> BacktestResult:
        n = len(pnls)
        if n == 0:
            return BacktestResult(
                symbol=self._symbol, strategy=self._strategy,
                n_trades=0, sharpe=0.0, max_dd=0.0,
                win_rate=0.0, profit_factor=0.0,
                total_pnl=0.0, equity_curve=equity_curve,
            )

        arr     = np.array(pnls, dtype=float)
        wins    = float(np.sum(arr > 0))
        gross_p = float(np.sum(arr[arr > 0]))
        gross_l = float(abs(np.sum(arr[arr < 0])))
        pf      = (gross_p / gross_l) if gross_l > 0 else float("inf")

        eq        = np.array(equity_curve, dtype=float)
        running   = np.maximum.accumulate(eq)
        dd_series = (1.0 - eq / running) * 100.0
        max_dd    = float(np.max(dd_series))

        returns = arr / self._equity0
        sharpe  = (float(np.mean(returns)) / float(np.std(returns)) * np.sqrt(252 * 96)
                   if float(np.std(returns)) > 0 else 0.0)

        return BacktestResult(
            symbol=self._symbol, strategy=self._strategy,
            n_trades=n, sharpe=round(sharpe, 4),
            max_dd=round(max_dd, 4),
            win_rate=round(wins / n, 4),
            profit_factor=round(pf, 4),
            total_pnl=round(float(np.sum(arr)), 6),
            equity_curve=[round(e, 2) for e in equity_curve],
        )
