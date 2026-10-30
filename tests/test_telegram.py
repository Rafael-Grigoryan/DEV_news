import pytest
import requests

from bot.telegram import TelegramError, TelegramPublisher
from tests.conftest import FakeResponse, FakeSession

TOKEN = "123:SECRET"
OK = FakeResponse(200, {"ok": True, "result": {"message_id": 42}})


def publisher(session, **kwargs):
    sleeps: list[float] = []
    return TelegramPublisher(TOKEN, "@chan", session=session, sleep=sleeps.append, **kwargs), sleeps


def test_payload():
    session = FakeSession([OK])
    pub, _ = publisher(session, disable_web_page_preview=True)
    assert pub.send("<b>hi</b>") == 42
    request = session.requests[0]
    assert request["url"] == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert request["json"] == {
        "chat_id": "@chan",
        "text": "<b>hi</b>",
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }


def test_429_waits_retry_after():
    too_many = FakeResponse(429, {"ok": False, "description": "Too Many Requests: retry after 11",
                                  "parameters": {"retry_after": 11}})
    session = FakeSession([too_many, OK])
    pub, sleeps = publisher(session)
    assert pub.send("x") == 42
    assert sleeps == [12.0]


def test_400_is_not_retried():
    session = FakeSession([FakeResponse(400, {"ok": False, "description": "Bad Request: chat not found"})])
    pub, sleeps = publisher(session)
    with pytest.raises(TelegramError, match="chat not found"):
        pub.send("x")
    assert sleeps == []


def test_5xx_retried_then_fails():
    session = FakeSession([FakeResponse(502, {"ok": False, "description": "Bad Gateway"})] * 3)
    pub, sleeps = publisher(session, max_retries=2)
    with pytest.raises(TelegramError, match="Bad Gateway"):
        pub.send("x")
    assert len(sleeps) == 2


def test_token_is_redacted_from_errors():
    err = requests.ConnectionError(f"Max retries exceeded with url: /bot{TOKEN}/sendMessage")
    session = FakeSession([err, err])
    pub, _ = publisher(session, max_retries=1)
    with pytest.raises(TelegramError) as info:
        pub.send("x")
    assert "SECRET" not in str(info.value)
    assert "/bot***/sendMessage" in str(info.value)
