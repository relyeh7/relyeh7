import requests

TELEGRAM_API = "https://api.telegram.org"


class TelegramClient:
    def __init__(self, token: str, chat_id: str):
        self._token   = token
        self._chat_id = chat_id

    def send(self, message: str) -> bool:
        if not self._token or not self._chat_id:
            return False
        try:
            r = requests.post(
                f"{TELEGRAM_API}/bot{self._token}/sendMessage",
                json={"chat_id": self._chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            return r.json().get("ok", False)
        except Exception as e:
            print(f"[Telegram] send error: {e}")
            return False
