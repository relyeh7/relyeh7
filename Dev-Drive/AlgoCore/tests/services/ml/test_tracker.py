import sys
from unittest.mock import MagicMock


def _make_mock_mlflow(run_id="abc123"):
    mock_mlflow = MagicMock()
    mock_sklearn = MagicMock()
    mock_run = MagicMock()
    mock_run.info.run_id = run_id
    mock_mlflow.start_run.return_value = mock_run
    return mock_mlflow, mock_sklearn


def _fresh_tracker(mock_mlflow, mock_sklearn, tracking_uri="mlruns", exp="test-exp"):
    # Remove cached module so __init__ re-runs imports
    sys.modules.pop("services.ml.tracking.mlflow_tracker", None)
    with _patch_mlflow(mock_mlflow, mock_sklearn):
        from services.ml.tracking.mlflow_tracker import MLflowTracker
        tracker = MLflowTracker(tracking_uri, exp)
    return tracker


class _patch_mlflow:
    def __init__(self, mock_mlflow, mock_sklearn):
        self._mock = mock_mlflow
        self._sk = mock_sklearn

    def __enter__(self):
        sys.modules["mlflow"] = self._mock
        sys.modules["mlflow.sklearn"] = self._sk
        return self

    def __exit__(self, *_):
        sys.modules.pop("mlflow", None)
        sys.modules.pop("mlflow.sklearn", None)
        sys.modules.pop("services.ml.tracking.mlflow_tracker", None)


def test_mlflow_tracker_start_run_returns_run_id():
    mock_mlflow, mock_sklearn = _make_mock_mlflow("abc123")
    tracker = _fresh_tracker(mock_mlflow, mock_sklearn)
    run_id = tracker.start_run("test-run")
    assert isinstance(run_id, str)
    assert run_id == "abc123"


def test_mlflow_tracker_log_metrics_calls_mlflow():
    mock_mlflow, mock_sklearn = _make_mock_mlflow("r1")
    tracker = _fresh_tracker(mock_mlflow, mock_sklearn)
    tracker.log_metrics({"sharpe": 1.5, "accuracy": 0.62})
    mock_mlflow.log_metrics.assert_called_once_with({"sharpe": 1.5, "accuracy": 0.62})
