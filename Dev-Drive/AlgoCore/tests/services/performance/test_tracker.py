from unittest.mock import patch


def _trade(pnl: float, strategy: str = "ml") -> dict:
    return {
        "id": "t1", "symbol": "BTCUSDT", "side": "buy",
        "entry_price": 50000.0, "exit_price": 51000.0,
        "size": 0.01, "pnl": pnl, "strategy": strategy,
        "opened_at": "2026-01-01T00:00:00+00:00",
        "closed_at": "2026-01-01T01:00:00+00:00",
    }


def test_tracker_on_trade_updates_stats():
    with patch("services.performance.tracker.set_state"), \
         patch("services.performance.tracker.publish"):
        from services.performance.tracker import PerformanceTracker
        pt = PerformanceTracker()
        pt.on_trade(_trade(10.0))
        pt.on_trade(_trade(20.0))
        stats = pt.get_stats("ml")
    assert stats["n_trades"] == 2
    assert stats["total_pnl"] == 30.0
    assert stats["win_rate"] == 1.0


def test_tracker_win_rate_counts_losses():
    with patch("services.performance.tracker.set_state"), \
         patch("services.performance.tracker.publish"):
        from services.performance.tracker import PerformanceTracker
        pt = PerformanceTracker()
        pt.on_trade(_trade(10.0))
        pt.on_trade(_trade(-5.0))
        stats = pt.get_stats("ml")
    assert stats["win_rate"] == 0.5
    assert stats["total_pnl"] == 5.0


def test_tracker_unknown_strategy_returns_zeros():
    with patch("services.performance.tracker.set_state"), \
         patch("services.performance.tracker.publish"):
        from services.performance.tracker import PerformanceTracker
        pt = PerformanceTracker()
        stats = pt.get_stats("nonexistent")
    assert stats["n_trades"] == 0
    assert stats["win_rate"] == 0.0


def test_tracker_run_uses_subscribe_since():
    """Ensure run() calls subscribe_since so cursor tracking is correct."""
    import services.performance.tracker as mod
    with patch.object(mod, "subscribe_since", return_value=([], "0")) as mock_sub, \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"):
        from services.performance.tracker import PerformanceTracker
        tracker = PerformanceTracker()
        # Run one iteration by patching sleep to raise after first call
        import itertools
        call_count = itertools.count()
        def one_shot(*a, **kw):
            if next(call_count) >= 1:
                raise SystemExit
        with patch("time.sleep", side_effect=one_shot):
            try:
                tracker.run()
            except SystemExit:
                pass
    mock_sub.assert_called()
