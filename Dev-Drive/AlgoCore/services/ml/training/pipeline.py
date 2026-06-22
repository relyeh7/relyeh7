from services.ml.data.fetcher import OHLCVFetcher
from services.ml.features import build_features
from services.ml.models.xgboost_model import XGBoostModel
from services.ml.tracking.mlflow_tracker import MLflowTracker


class TrainingPipeline:
    _ARTIFACT = "xgb_model"

    def __init__(
        self,
        symbol: str,
        exchange: str,
        tracker: MLflowTracker,
        fetcher: OHLCVFetcher | None = None,
        model: XGBoostModel | None = None,
    ):
        self._symbol   = symbol
        self._exchange = exchange
        self._tracker  = tracker
        self._fetcher  = fetcher or OHLCVFetcher()
        self._model    = model  or XGBoostModel()

    def run(self, min_sharpe: float = 1.0) -> bool:
        raw = self._fetcher.get_candles(self._symbol, exchange=self._exchange, limit=500)
        df  = build_features(raw)

        run_id = self._tracker.start_run(f"{self._symbol}_xgb")
        self._tracker.log_params({
            "symbol": self._symbol, "exchange": self._exchange,
            "n_rows": len(df), "min_sharpe": min_sharpe,
        })

        metrics = self._model.fit(df)
        self._tracker.log_metrics(metrics)

        promoted = metrics["sharpe"] >= min_sharpe
        if promoted:
            self._tracker.log_model(self._model._clf, self._ARTIFACT)
            reg_name = f"algocore-{self._symbol.lower()}-xgb"
            self._tracker.register_model(run_id, self._ARTIFACT, reg_name)
            print(f"[Pipeline] {self._symbol} promoted: Sharpe={metrics['sharpe']:.3f}")
        else:
            print(f"[Pipeline] {self._symbol} not promoted: Sharpe={metrics['sharpe']:.3f} < {min_sharpe}")

        self._tracker.end_run()
        return promoted
