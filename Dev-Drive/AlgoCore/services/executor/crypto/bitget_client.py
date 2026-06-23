import hmac
import hashlib
import base64
import time
import requests
from shared.config import settings


class BitgetClient:
    BASE = "https://api.bitget.com"

    def __init__(self):
        self._key        = settings.bitget_api_key
        self._secret     = settings.bitget_api_secret
        self._passphrase = settings.bitget_api_passphrase

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        msg = timestamp + method.upper() + path + body
        return base64.b64encode(
            hmac.new(self._secret.encode(), msg.encode(), hashlib.sha256).digest()
        ).decode()

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        ts = str(int(time.time() * 1000))
        return {
            "ACCESS-KEY":        self._key,
            "ACCESS-SIGN":       self._sign(ts, method, path, body),
            "ACCESS-TIMESTAMP":  ts,
            "ACCESS-PASSPHRASE": self._passphrase,
            "Content-Type":      "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict:
        r = requests.get(self.BASE + path, params=params,
                         headers=self._headers("GET", path), timeout=10)
        r.raise_for_status()
        return r.json().get("data", {})

    def _post(self, path: str, body: dict) -> dict:
        import json
        b = json.dumps(body)
        r = requests.post(self.BASE + path, data=b,
                          headers=self._headers("POST", path, b), timeout=10)
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") != "00000":
            raise ValueError(f"Bitget error {resp.get('code')}: {resp.get('msg')}")
        return resp.get("data", {})

    def get_ticker(self, symbol: str) -> float:
        data = self._get("/api/v2/spot/market/tickers", {"symbol": symbol})
        items = data if isinstance(data, list) else [data]
        return float(items[0]["lastPr"])

    def get_balance(self, coin: str) -> float:
        items = self._get("/api/v2/spot/account/assets") or []
        for item in items:
            if item.get("coin") == coin:
                return float(item.get("available", 0))
        return 0.0

    def place_order(self, symbol: str, side: str, price: float, size: float) -> str:
        data = self._post("/api/v2/spot/trade/place-order", {
            "symbol": symbol, "side": side,
            "orderType": "limit",
            "price": str(round(price, 2)),
            "size":  str(round(size, 6)),
            "force": "gtc",
        })
        return data.get("orderId", "")

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        self._post("/api/v2/spot/trade/cancel-order",
                   {"symbol": symbol, "orderId": order_id})
        return True

    def get_order_status(self, order_id: str, symbol: str) -> str:
        try:
            data = self._get("/api/v2/spot/trade/orderInfo",
                             {"orderId": order_id, "symbol": symbol})
            items = data if isinstance(data, list) else [data]
            raw = items[0].get("status", "live") if items else "live"
            if raw == "filled":
                return "filled"
            if raw == "cancelled":
                return "cancelled"
            return "pending"
        except Exception:
            return "pending"
