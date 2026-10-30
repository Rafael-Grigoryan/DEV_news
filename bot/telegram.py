from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)


class TelegramError(Exception):
    pass


class TelegramPublisher:
    """sendMessage с parse_mode=HTML; 429 ждёт retry_after, 5xx и сетевые ошибки — backoff."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        disable_web_page_preview: bool = True,
        timeout: float = 30.0,
        max_retries: int = 5,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ):
        self.token = token
        self.chat_id = chat_id
        self.disable_web_page_preview = disable_web_page_preview
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self._sleep = sleep

    def send(self, text: str) -> int:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": self.disable_web_page_preview},
        }
        error = ""
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.post(url, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                error, delay = f"сетевая ошибка: {exc}", min(30, 2 ** (attempt + 1))
            else:
                try:
                    data = resp.json()
                except ValueError:
                    data = {}
                if resp.status_code == 200 and data.get("ok"):
                    return data["result"]["message_id"]
                error = f"HTTP {resp.status_code}: {data.get('description') or resp.text[:200]}"
                if resp.status_code == 429:
                    delay = float((data.get("parameters") or {}).get("retry_after", 5)) + 1
                elif resp.status_code >= 500:
                    delay = min(30, 2 ** (attempt + 1))
                else:
                    # 400 (разметка, chat not found), 401 (токен), 403 (бот не админ): повтор не поможет.
                    raise TelegramError(self._redact(error))
            if attempt < self.max_retries:
                log.warning("Telegram: %s, повтор через %.0f с", self._redact(error), delay)
                self._sleep(delay)
        raise TelegramError(self._redact(error))

    def _redact(self, text: str) -> str:
        return text.replace(self.token, "***") if self.token else text
