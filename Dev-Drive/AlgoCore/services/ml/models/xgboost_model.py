import numpy as np
import pandas as pd
import xgboost as xgb
from services.ml.features import FEATURE_COLS


class XGBoostModel:
    def __init__(self):
        self._clf = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
        )
        self._trained = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def fit(self, df: pd.DataFrame) -> dict:
        X = df[FEATURE_COLS].values
        y = df["target"].values
        split = int(len(X) * 0.8)
        X_train, X_oos = X[:split], X[split:]
        y_train, y_oos = y[:split], y[split:]
        self._clf.fit(X_train, y_train)
        self._trained = True
        accuracy = float((self._clf.predict(X_oos) == y_oos).mean()) if len(X_oos) else 0.0
        sharpe = self._calc_sharpe(y_oos, self._clf.predict_proba(X_oos)[:, 1]) if len(X_oos) else 0.0
        return {"accuracy": accuracy, "sharpe": sharpe}

    def predict(self, df: pd.DataFrame) -> float:
        X = df[FEATURE_COLS].values
        return float(self._clf.predict_proba(X)[0, 1])

    def save(self, path: str) -> None:
        self._clf.save_model(path)

    def load(self, path: str) -> None:
        self._clf.load_model(path)
        self._trained = True

    @staticmethod
    def _calc_sharpe(y_true: np.ndarray, y_proba: np.ndarray) -> float:
        if len(y_true) == 0:
            return 0.0
        signals = np.where(y_proba > 0.5, 1, -1)
        actual  = np.where(y_true == 1, 1, -1)
        returns = signals * actual * 0.001
        std = returns.std()
        if std == 0:
            return 0.0
        return float(returns.mean() / std * np.sqrt(252 * 96))
