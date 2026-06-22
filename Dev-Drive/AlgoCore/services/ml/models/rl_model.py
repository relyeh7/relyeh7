import random
from collections import deque
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from services.ml.features import FEATURE_COLS

_ACTIONS = {0: "HOLD", 1: "BUY", 2: "SELL"}


class _DQNNet(nn.Module):
    def __init__(self, state_size: int, action_size: int, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_size, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden),    nn.ReLU(),
            nn.Linear(hidden, action_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class RLModel:
    def __init__(self, state_size: int = 10, action_size: int = 3,
                 lr: float = 1e-3, gamma: float = 0.99):
        self._state_size  = state_size
        self._action_size = action_size
        self._gamma       = gamma
        self._net         = _DQNNet(state_size, action_size)
        self._target_net  = _DQNNet(state_size, action_size)
        self._target_net.load_state_dict(self._net.state_dict())
        self._optimizer   = torch.optim.Adam(self._net.parameters(), lr=lr)
        self._buffer: deque = deque(maxlen=10_000)
        self._trained     = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def fit(self, df: pd.DataFrame, episodes: int = 20) -> dict:
        X = df[FEATURE_COLS].values.astype(np.float32)
        y = df["target"].values.astype(np.int64)
        rewards_history: list[float] = []

        for ep in range(episodes):
            epsilon = max(0.1, 1.0 - ep / max(episodes, 1))
            ep_reward = 0.0
            for i in range(len(X) - 1):
                action = self._select_action(X[i], epsilon)
                actual = int(y[i])
                if action == 1:    # BUY
                    reward = 1.0 if actual == 1 else -1.0
                elif action == 2:  # SELL
                    reward = 1.0 if actual == 0 else -1.0
                else:              # HOLD
                    reward = 0.0
                done = i == len(X) - 2
                self._buffer.append((X[i], action, reward, X[i + 1], float(done)))
                ep_reward += reward
                if len(self._buffer) >= 32:
                    self._train_step()
            rewards_history.append(ep_reward)

        self._target_net.load_state_dict(self._net.state_dict())
        self._trained = True
        avg = float(np.mean(rewards_history[-min(10, len(rewards_history)):]))
        return {"avg_reward": avg, "episodes": episodes}

    def predict(self, df: pd.DataFrame) -> tuple[str, float]:
        state = torch.FloatTensor(df[FEATURE_COLS].iloc[-1].values)
        self._net.eval()
        with torch.no_grad():
            q_vals = self._net(state)
            idx    = int(q_vals.argmax().item())
            probs  = torch.softmax(q_vals, dim=0)
            conf   = float(probs[idx].item())
        return _ACTIONS[idx], conf

    def save(self, path: str) -> None:
        torch.save(self._net.state_dict(), path)

    def load(self, path: str) -> None:
        self._net.load_state_dict(torch.load(path, weights_only=True))
        self._target_net.load_state_dict(self._net.state_dict())
        self._trained = True

    def _select_action(self, state: np.ndarray, epsilon: float) -> int:
        if random.random() < epsilon:
            return random.randint(0, self._action_size - 1)
        with torch.no_grad():
            q = self._net(torch.FloatTensor(state))
            return int(q.argmax().item())

    def _train_step(self) -> None:
        batch      = random.sample(self._buffer, 32)
        states     = torch.FloatTensor([b[0] for b in batch])
        actions    = torch.LongTensor([b[1] for b in batch])
        rewards    = torch.FloatTensor([b[2] for b in batch])
        next_states= torch.FloatTensor([b[3] for b in batch])
        dones      = torch.FloatTensor([b[4] for b in batch])

        q_values   = self._net(states).gather(1, actions.unsqueeze(1)).squeeze()
        with torch.no_grad():
            next_q = self._target_net(next_states).max(1)[0]
            target = rewards + self._gamma * next_q * (1.0 - dones)

        loss = nn.functional.mse_loss(q_values, target)
        self._optimizer.zero_grad()
        loss.backward()
        self._optimizer.step()
