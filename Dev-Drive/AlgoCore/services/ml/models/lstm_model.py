import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from services.ml.features import FEATURE_COLS


class _LSTMNet(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc   = nn.Linear(hidden_size, 1)
        self.sig  = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.sig(self.fc(out[:, -1, :]))


class LSTMModel:
    def __init__(self, input_size: int = 10, hidden_size: int = 64,
                 num_layers: int = 2, seq_len: int = 20):
        self._net     = _LSTMNet(input_size, hidden_size, num_layers)
        self._seq_len = seq_len
        self._trained = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def fit(self, df: pd.DataFrame, epochs: int = 30) -> dict:
        X, y = self._make_sequences(df)
        if len(X) == 0:
            return {"accuracy": 0.0, "sharpe": 0.0}
        split    = int(len(X) * 0.8)
        X_t, y_t = torch.FloatTensor(X[:split]), torch.FloatTensor(y[:split]).unsqueeze(1)
        X_v, y_v = torch.FloatTensor(X[split:]), torch.FloatTensor(y[split:])
        opt     = torch.optim.Adam(self._net.parameters(), lr=1e-3)
        loss_fn = nn.BCELoss()
        self._net.train()
        for _ in range(epochs):
            opt.zero_grad()
            pred = self._net(X_t)
            loss_fn(pred, y_t).backward()
            opt.step()
        self._trained = True
        self._net.eval()
        with torch.no_grad():
            proba = self._net(torch.FloatTensor(X[split:])).squeeze().numpy()
        if proba.ndim == 0:
            proba = np.array([float(proba)])
        preds  = (proba > 0.5).astype(int)
        acc    = float((preds == y_v.numpy()).mean()) if len(preds) else 0.0
        sharpe = self._calc_sharpe(y_v.numpy(), proba)
        return {"accuracy": acc, "sharpe": sharpe}

    def predict(self, df: pd.DataFrame) -> float:
        X, _ = self._make_sequences(df, has_target=False)
        if len(X) == 0:
            return 0.5
        self._net.eval()
        with torch.no_grad():
            return float(self._net(torch.FloatTensor(X[-1:])).squeeze())

    def save(self, path: str) -> None:
        torch.save(self._net.state_dict(), path)

    def load(self, path: str) -> None:
        self._net.load_state_dict(torch.load(path, weights_only=True))
        self._trained = True

    def _make_sequences(self, df: pd.DataFrame, has_target: bool = True):
        X_raw  = df[FEATURE_COLS].values.astype(float)
        y_raw  = df["target"].values.astype(float) if has_target and "target" in df.columns else None
        seqs, targets = [], []
        for i in range(self._seq_len, len(X_raw)):
            seqs.append(X_raw[i - self._seq_len:i])
            if y_raw is not None:
                targets.append(y_raw[i])
        return np.array(seqs), np.array(targets)

    @staticmethod
    def _calc_sharpe(y_true: np.ndarray, y_proba: np.ndarray) -> float:
        if len(y_true) == 0:
            return 0.0
        signals = np.where(y_proba > 0.5, 1, -1)
        actual  = np.where(y_true == 1, 1, -1)
        returns = signals * actual * 0.001
        std = returns.std()
        return float(returns.mean() / std * np.sqrt(252 * 96)) if std > 0 else 0.0
