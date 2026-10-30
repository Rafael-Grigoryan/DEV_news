from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import requests

from bot import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"changelog-telegram-bot/{__version__} (+https://github.com)"


class FetchError(Exception):
    pass


class HttpClient:
    """GET с ретраями на сетевые ошибки, 429 и 5xx. Токен GitHub — только для api.github.com."""

    def __init__(
        self,
        timeout: float = 30.0,
        retries: int = 2,
        github_token: str | None = None,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ):
        self.timeout = timeout
        self.retries = retries
        self.github_token = github_token
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._sleep = sleep

    def get(self, url: str, headers: dict[str, str] | None = None) -> requests.Response:
        headers = dict(headers or {})
        if self.github_token and urlparse(url).hostname == "api.github.com":
            headers.setdefault("Authorization", f"Bearer {self.github_token}")
        error = ""
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
            except requests.RequestException as exc:
                error = f"{type(exc).__name__}: {exc}"
            else:
                if resp.ok:
                    return resp
                error = f"HTTP {resp.status_code}"
                if resp.status_code != 429 and resp.status_code < 500:
                    break
            if attempt < self.retries:
                delay = 2 * (attempt + 1)
                log.debug("GET %s: %s, повтор через %ss", url, error, delay)
                self._sleep(delay)
        raise FetchError(f"GET {url}: {error}")

    def get_text(self, url: str) -> str:
        resp = self.get(url)
        if "charset" not in resp.headers.get("Content-Type", "").lower():
            # Без charset requests берёт ISO-8859-1 для text/*; все наши источники в UTF-8.
            return resp.content.decode("utf-8", errors="replace")
        return resp.text

    def get_bytes(self, url: str) -> bytes:
        return self.get(url).content
