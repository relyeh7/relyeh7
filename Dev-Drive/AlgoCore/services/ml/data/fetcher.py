import requests
import pandas as pd
from datetime import datetime, timezone


class OHLCVFetcher:
    _BITGET_BASE  = "https://api.bitget.com"
    _BINANCE_BASE = "https://api.binance.com"

    def get_candles(
        self,
        symbol: str,
        exchange: str = "bitget",
        interval: str = "15m",
        limit: int = 200,
    ) -> pd.DataFrame:
        if exchange == "bitget":
            return self._bitget(symbol, interval, limit)
        if exchange == "binance":
            return self._binance(symbol, interval, limit)
        raise ValueError(f"Unknown exchange: {exchange}")

    def _bitget(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        gran = interval.replace("m", "min").replace("h", "H")
        r = requests.get(
            f"{self._BITGET_BASE}/api/v2/spot/market/candles",
            params={"symbol": symbol, "granularity": gran, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") != "00000":
            raise ValueError(f"Bitget error: {resp.get('msg')}")
        rows = []
        for raw in resp["data"]:
            ts_ms = int(raw[0])
            ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            rows.append({
                "timestamp": ts_iso,
                "open":   float(raw[1]),
                "high":   float(raw[2]),
                "low":    float(raw[3]),
                "close":  float(raw[4]),
                "volume": float(raw[5]),
            })
        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        return df

    def _binance(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        r = requests.get(
            f"{self._BINANCE_BASE}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        rows = []
        for raw in r.json():
            ts_ms = int(raw[0])
            ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            rows.append({
                "timestamp": ts_iso,
                "open":   float(raw[1]),
                "high":   float(raw[2]),
                "low":    float(raw[3]),
                "close":  float(raw[4]),
                "volume": float(raw[5]),
            })
        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        return df
