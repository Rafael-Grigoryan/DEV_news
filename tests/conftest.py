from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bot.config import Settings, SourceConfig

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_source(**overrides) -> SourceConfig:
    raw = {"id": "test", "name": "Test", "type": "markdown_changelog", "url": "https://example.com/CHANGELOG.md"}
    raw.update(overrides)
    return SourceConfig.from_dict(raw, Settings())


class FakeHttp:
    """Подмена HttpClient: url -> текст (или исключение)."""

    def __init__(self, routes: dict[str, str | Exception] | None = None):
        self.routes = routes or {}
        self.calls: list[str] = []

    def _get(self, url: str):
        self.calls.append(url)
        value = self.routes[url]
        if isinstance(value, Exception):
            raise value
        return value

    def get_text(self, url: str) -> str:
        return self._get(url)

    def get_bytes(self, url: str) -> bytes:
        return self._get(url).encode("utf-8")


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload) if payload is not None else ""

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Отдаёт заранее заданные ответы по очереди и запоминает запросы."""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def post(self, url, **kwargs):
        # Копия: requests сериализует тело в момент вызова, последующие изменения dict не видны.
        self.requests.append(copy.deepcopy({"url": url, **kwargs}))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def no_sleep():
    calls: list[float] = []
    return calls.append, calls
