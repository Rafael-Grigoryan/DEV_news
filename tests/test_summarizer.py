import requests

from bot.models import Entry
from bot.summarizer import (
    API_URL,
    DEFAULT_MODELS,
    GeminiSummarizer,
    extract_text,
    fallback_summary,
    is_russian,
    markdown_to_items,
    parse_items,
    parse_models,
)
from tests.conftest import FakeResponse, FakeSession, make_source, read_fixture

SOURCE = make_source(name="Dart")
ENTRY = Entry("dart", "3.13.7", "Dart 3.13.7", "- Fixed `dart:io` bug\n- Added a thing", "https://x")

# Форма ответа из документации Interactions API
OK_PAYLOAD = {
    "id": "v1_x",
    "model": "gemini-3.8-flash",
    "object": "interaction",
    "status": "completed",
    "steps": [
        {"type": "thought", "content": [{"type": "text", "text": "размышления"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "- Исправлена ошибка в `dart:io`\n- Добавлена штука"}]},
    ],
}


def summarizer(session, **kwargs):
    sleeps: list[float] = []
    kwargs.setdefault("min_interval", 0)  # паузы троттлинга проверяются отдельным тестом
    kwargs.setdefault("models", ["m1"])  # цепочка моделей проверяется отдельными тестами
    s = GeminiSummarizer("KEY", session=session, sleep=sleeps.append, clock=lambda: 0.0, **kwargs)
    return s, sleeps


def test_extract_text_ignores_thoughts():
    assert extract_text(OK_PAYLOAD) == "- Исправлена ошибка в `dart:io`\n- Добавлена штука"


def test_parse_items_drops_intro_and_joins_wrapped_lines():
    text = "Вот выжимка:\n\n- Первый пункт\n  продолжение\n* Второй\n1. Третий\n• Четвёртый"
    assert parse_items(text) == ["Первый пункт продолжение", "Второй", "Третий", "Четвёртый"]


def test_parse_items_without_bullets_keeps_lines():
    assert parse_items("Просто перевод одной строки.") == ["Просто перевод одной строки."]


def test_successful_summary_and_request_shape():
    session = FakeSession([FakeResponse(200, OK_PAYLOAD)])
    s, _ = summarizer(session, models="gemini-test")
    summary = s.summarize(ENTRY, SOURCE)
    assert summary.translated
    assert summary.items == ["Исправлена ошибка в `dart:io`", "Добавлена штука"]
    request = session.requests[0]
    assert request["url"] == API_URL
    assert request["headers"]["x-goog-api-key"] == "KEY"
    assert request["json"]["model"] == "gemini-test"
    assert request["json"]["store"] is False
    assert "Dart 3.13.7" in request["json"]["input"] and "Fixed `dart:io` bug" in request["json"]["input"]


def test_retry_on_429_uses_retry_info():
    rate_limited = FakeResponse(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"}]}})
    session = FakeSession([rate_limited, FakeResponse(200, OK_PAYLOAD)])
    s, sleeps = summarizer(session)
    assert s.summarize(ENTRY, SOURCE).translated
    assert 7.0 in sleeps


def test_long_retry_delay_means_quota_exhausted_and_disables_gemini():
    rate_limited = FakeResponse(429, {"error": {"details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3600s"}]}})
    session = FakeSession([rate_limited])
    s, _ = summarizer(session)
    assert not s.summarize(ENTRY, SOURCE).translated
    assert not s.summarize(ENTRY, SOURCE).translated
    assert len(session.requests) == 1  # второй раз Gemini уже не дёргаем


def test_retries_on_5xx_then_fallback():
    session = FakeSession([FakeResponse(503, {"error": {"message": "overloaded"}})] * 3)
    s, sleeps = summarizer(session, max_retries=2)
    summary = s.summarize(ENTRY, SOURCE)
    assert not summary.translated
    assert summary.items == ["Fixed `dart:io` bug", "Added a thing"]
    assert len(session.requests) == 3
    assert len(sleeps) == 2


# Реальные ответы gemini-3.5-flash-lite из замера
RU_ANSWER = [
    "В `dart:io` на Android 14+ теперь используется обновляемое хранилище корневых сертификатов "
    "Conscrypt APEX для поддержки изменений корневых CA через обновления системы Google Play.",
    "Обновлен BoringSSL для включения актуальных исправлений безопасности, включая блокировку "
    "скомпрометированных промежуточных сертификатов и исправления проверки путей X.509.",
]
EN_ANSWER = [
    "Added `permissions.blockWritesOutsideWorkingDirectories` to reject paths outside working "
    "directories in all permission modes.",
    "Fixed `claude -p` exiting with code `0` and no output on startup failure, it now prints the error and exits `1`.",
]


def test_is_russian_on_real_answers():
    assert is_russian(RU_ANSWER)
    assert not is_russian(EN_ANSWER)
    assert is_russian(["Новый флаг `--very-long-english-flag-name-here` для `claude mcp add`"])


def test_english_answer_goes_to_next_model():
    english = {**OK_PAYLOAD, "steps": [{"type": "model_output", "content": [
        {"type": "text", "text": "\n".join(f"- {line}" for line in EN_ANSWER)}]}]}
    session = FakeSession([FakeResponse(200, english), FakeResponse(200, OK_PAYLOAD), FakeResponse(200, OK_PAYLOAD)])
    s, _ = summarizer(session, models="lite,flash")
    assert s.summarize(ENTRY, SOURCE).translated
    assert [r["json"]["model"] for r in session.requests] == ["lite", "flash"]
    # «не на русском» — проблема записи, а не модели: следующая запись снова начинается с lite
    s.summarize(ENTRY, SOURCE)
    assert session.requests[-1]["json"]["model"] == "lite"

    session = FakeSession([FakeResponse(200, english)])
    s, _ = summarizer(session)
    assert not s.summarize(ENTRY, SOURCE).translated


def test_overloaded_model_is_skipped_for_rest_of_run():
    overloaded = FakeResponse(503, {"error": {"message": "gemini-3.8-flash is currently experiencing high demand"}})
    session = FakeSession([overloaded, overloaded, FakeResponse(200, OK_PAYLOAD), FakeResponse(200, OK_PAYLOAD)])
    s, sleeps = summarizer(session, models=["big", "small"], max_retries=1)
    assert s.summarize(ENTRY, SOURCE).translated
    assert [r["json"]["model"] for r in session.requests] == ["big", "big", "small"]
    assert len(sleeps) == 1  # одна пауза перед повтором big
    assert s.summarize(ENTRY, SOURCE).translated
    assert session.requests[-1]["json"]["model"] == "small"


def test_timeout_and_missing_model_switch_immediately():
    session = FakeSession([requests.ReadTimeout("slow"), FakeResponse(404, {"error": {"message": "not found"}}),
                           FakeResponse(200, OK_PAYLOAD)])
    s, sleeps = summarizer(session, models="hanging,typo,ok", max_retries=3)
    assert s.summarize(ENTRY, SOURCE).translated
    assert [r["json"]["model"] for r in session.requests] == ["hanging", "typo", "ok"]
    assert sleeps == []


def test_all_models_unavailable_disables_gemini():
    session = FakeSession([requests.ReadTimeout("slow"), requests.ReadTimeout("slow")])
    s, _ = summarizer(session, models="a,b")
    assert not s.summarize(ENTRY, SOURCE).translated
    assert not s.summarize(ENTRY, SOURCE).translated
    assert len(session.requests) == 2


def test_parse_models():
    assert parse_models(" gemini-a , gemini-b,, ") == ["gemini-a", "gemini-b"]
    assert parse_models("") == list(DEFAULT_MODELS)
    assert parse_models(None) == list(DEFAULT_MODELS)


def test_unsupported_thinking_level_is_dropped():
    unsupported = FakeResponse(400, {"error": {
        "message": "Thinking level THINKING_LEVEL_LOW is not supported for this model.", "code": "invalid_request"}})
    session = FakeSession([unsupported, FakeResponse(200, OK_PAYLOAD), FakeResponse(200, OK_PAYLOAD)])
    s, _ = summarizer(session)
    assert s.summarize(ENTRY, SOURCE).translated
    assert s.summarize(ENTRY, SOURCE).translated
    configs = [r["json"]["generation_config"] for r in session.requests]
    assert "thinking_level" in configs[0]
    assert all("thinking_level" not in c for c in configs[1:])


def test_time_budget_stops_hanging_requests():
    now = [0.0]

    class HangingSession:
        calls = 0

        def post(self, url, **kwargs):
            HangingSession.calls += 1
            now[0] += kwargs["timeout"]  # каждый запрос висит до таймаута
            raise requests.ReadTimeout("read timed out")

    s = GeminiSummarizer("KEY", ["a", "b", "c"], session=HangingSession(), sleep=lambda _: None,
                         clock=lambda: now[0], min_interval=0, timeout=90, time_budget=150)
    assert not s.summarize(ENTRY, SOURCE).translated
    # a висит 90 с, b — остаток бюджета 60 с, на c бюджета уже нет
    assert HangingSession.calls == 2
    assert now[0] <= 150
    assert not s.summarize(ENTRY, SOURCE).translated
    assert HangingSession.calls == 2  # до конца прогона Gemini больше не дёргаем


def test_network_error_falls_back():
    session = FakeSession([requests.ConnectionError("boom")] * 2)
    s, _ = summarizer(session, max_retries=1)
    assert not s.summarize(ENTRY, SOURCE).translated


def test_bad_key_disables_without_retries():
    session = FakeSession([FakeResponse(400, {"error": {"message": "API key not valid"}})])
    s, sleeps = summarizer(session)
    assert not s.summarize(ENTRY, SOURCE).translated
    assert len(session.requests) == 1 and sleeps == []


def test_unexpected_response_shape_falls_back():
    session = FakeSession([FakeResponse(200, {"status": "completed", "steps": ["weird"]})])
    s, _ = summarizer(session)
    assert not s.summarize(ENTRY, SOURCE).translated


def test_no_api_key_uses_fallback_without_requests():
    session = FakeSession([])
    s = GeminiSummarizer(None, session=session)
    summary = s.summarize(ENTRY, SOURCE)
    assert not summary.translated
    assert session.requests == []


def test_min_interval_between_requests():
    now = [100.0]
    sleeps: list[float] = []
    session = FakeSession([FakeResponse(200, OK_PAYLOAD), FakeResponse(200, OK_PAYLOAD)])
    s = GeminiSummarizer("KEY", "m1", session=session, sleep=sleeps.append, clock=lambda: now[0], min_interval=4.0)
    s.summarize(ENTRY, SOURCE)
    now[0] += 1.0
    s.summarize(ENTRY, SOURCE)
    assert sleeps == [3.0]


def test_markdown_to_items_on_real_dart_entry():
    text = read_fixture("dart_stable_CHANGELOG.md").split("## 3.13.6")[0]
    items = markdown_to_items(text)
    assert "This is a patch release that:" in items
    conscrypt = next(i for i in items if i.startswith("Uses the updatable Conscrypt"))
    assert "\n" not in conscrypt and "Google Play system updates are honored. (issue #64696)" in conscrypt
    assert not any(i.startswith("#64696") or "https://" in i for i in items)  # сноски-ссылки убраны


def test_fallback_is_truncated():
    entry = Entry("s", "1", "T", "\n".join(f"- line {i} " + "x" * 50 for i in range(100)), "u")
    summary = fallback_summary(entry, max_chars=300)
    assert summary.items[-1] == "…"
    assert sum(len(i) for i in summary.items[:-1]) <= 300
