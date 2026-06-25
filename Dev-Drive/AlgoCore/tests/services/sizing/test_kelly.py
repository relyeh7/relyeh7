from unittest.mock import patch


def _perf(win_rate: float = 0.6, n_trades: int = 20, profit_factor: float = 1.8) -> dict:
    return {
        "n_trades":      n_trades,
        "win_rate":      win_rate,
        "sharpe":        1.2,
        "max_dd":        3.0,
        "total_pnl":     50.0,
        "profit_factor": profit_factor,
    }


def test_kelly_returns_positive_size_with_good_stats():
    with patch("services.sizing.kelly.get_state", return_value=_perf(0.6, 20, 1.8)), \
         patch("services.sizing.kelly.settings") as mock_s:
        mock_s.kelly_fraction = 0.25
        from services.sizing.kelly import KellySizer
        sizer = KellySizer(min_size=0.001)
        size = sizer.compute("ml")
    assert size > 0.001
    assert size <= 0.25


def test_kelly_returns_min_size_with_too_few_trades():
    with patch("services.sizing.kelly.get_state", return_value=_perf(0.6, 5, 1.8)), \
         patch("services.sizing.kelly.settings") as mock_s:
        mock_s.kelly_fraction = 0.25
        from services.sizing.kelly import KellySizer
        sizer = KellySizer(min_size=0.001)
        size = sizer.compute("ml")
    assert size == 0.001


def test_kelly_returns_min_size_when_no_perf_data():
    with patch("services.sizing.kelly.get_state", return_value=None):
        from services.sizing.kelly import KellySizer
        sizer = KellySizer(min_size=0.001)
        size = sizer.compute("unknown")
    assert size == 0.001


def test_kelly_capped_at_kelly_fraction():
    # win_rate=0.9, profit_factor=5 → Kelly would be huge; should be capped
    with patch("services.sizing.kelly.get_state", return_value=_perf(0.9, 50, 5.0)), \
         patch("services.sizing.kelly.settings") as mock_s:
        mock_s.kelly_fraction = 0.1
        from services.sizing.kelly import KellySizer
        sizer = KellySizer(min_size=0.001)
        size = sizer.compute("ml")
    assert size <= 0.1


def test_kelly_negative_edge_returns_min_size():
    # win_rate=0.3, profit_factor=0.5 → Kelly negative → use min_size
    with patch("services.sizing.kelly.get_state", return_value=_perf(0.3, 20, 0.5)), \
         patch("services.sizing.kelly.settings") as mock_s:
        mock_s.kelly_fraction = 0.25
        from services.sizing.kelly import KellySizer
        sizer = KellySizer(min_size=0.001)
        size = sizer.compute("ml")
    assert size == 0.001
