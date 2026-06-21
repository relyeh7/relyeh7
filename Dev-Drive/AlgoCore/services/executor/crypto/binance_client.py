import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode
from shared.config import settings


class BinanceClient:
    BASE = "https://api.binance.com"

    def __init__(self):
        self._key    = settings.binance_api_key
        self._secret = settings.binance_api_secret

    def _sign(self, params: dict) -> str:
        return hmac.new(
            self._secret.encode(),
            urlencode(params).encode(),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self._key}

    def get_ticker(self, symbol: str) -> float:
        r = requests.get(f"{self.BASE}/api/v3/ticker/price",
                         params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        return float(r.json()["price"])

    def get_balance(self, asset: str) -> float:
        ts = int(time.time() * 1000)
        params = {"timestamp": ts}
        params["signature"] = self._sign(params)
        r = requests.get(f"{self.BASE}/api/v3/account",
                         params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        for b in r.json():
            if b.get("asset") == asset:
                return float(b["free"])
        return 0.0

    def place_order(self, symbol: str, side: str, price: float, quantity: float) -> str:
        ts = int(time.time() * 1000)
        params = {
            "symbol":      symbol,
            "side":        side.upper(),
            "type":        "LIMIT",
            "timeInForce": "GTC",
            "price":       str(round(price, 2)),
            "quantity":    str(round(quantity, 6)),
            "timestamp":   ts,
        }
        params["signature"] = self._sign(params)
        r = requests.post(f"{self.BASE}/api/v3/order",
                          params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        body = r.json()
        if "orderId" not in body:
            raise ValueError(f"Binance order failed: {body}")
        return str(body["orderId"])
