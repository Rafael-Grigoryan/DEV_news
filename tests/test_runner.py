"""Дедупликация, первый запуск, лимиты, изоляция ошибок и dry-run."""

import io
import json

import pytest

from bot.config import Config, Settings, SourceConfig
from bot.models import Entry
from bot.parsers.base import Parser
from bot.runner import Runner
from bot.state import State
from bot.summarizer import GeminiSummarizer
from bot.telegram import TelegramError


class FakeParser(Parser):
    type = "fake"
    feeds: dict[str, list[Entry] | Exception] = {}

    def fetch(self):
        feed = self.feeds[self.source.id]
        if isinstance(feed, Exception):
            raise feed
        return list(feed)


class FakePublisher:
    def __init__(self, fail_on: set[str] = frozenset()):
        self.sent: list[str] = []
        self.fail_on = fail_on

    def send(self, text):
        if any(marker in text for marker in self.fail_on):
            raise TelegramError("HTTP 403: Forbidden: bot is not a member of the channel chat")
        self.sent.append(text)
        return len(self.sent)


def entries(source_id: str, versions: list[str]) -> list[Entry]:
    """Записи от новых к старым, как их отдают парсеры."""
    return [Entry(source_id, v, f"{source_id} {v}", f"- change in {v}", f"https://x/{v}") for v in versions]


def make_config(*sources: dict, **settings) -> Config:
    settings = Settings(post_delay_seconds=0, **settings)
    return Config(settings, [SourceConfig.from_dict({"type": "fake", "url": "https://x", "name": s["id"], **s},
                                                    settings) for s in sources])


def make_runner(tmp_path, config, feeds, publisher=None, **kwargs):
    FakeParser.feeds = feeds
    state = State(tmp_path / "state.json", keep=config.settings.state_keep)
    runner = Runner(
        config, state, http=None, summarizer=GeminiSummarizer(None), publisher=publisher,
        parser_factory=lambda source, http: FakeParser(source, http), out=io.StringIO(),
        sleep=lambda _: None, **kwargs,
    )
    return runner, state


def saved_seen(tmp_path, source_id):
    return json.loads((tmp_path / "state.json").read_text())["sources"][source_id]["seen"]


def test_first_run_only_remembers(tmp_path):
    pub = FakePublisher()
    runner, _ = make_runner(tmp_path, make_config({"id": "a"}), {"a": entries("a", ["3", "2", "1"])}, pub)
    report = runner.run()
    assert pub.sent == []
    assert report.sources[0].initialized
    assert saved_seen(tmp_path, "a") == ["1", "2", "3"]
    assert not report.failed


def test_first_run_publish_latest_on_init(tmp_path):
    pub = FakePublisher()
    config = make_config({"id": "a", "publish_latest_on_init": True})
    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["3", "2", "1"])}, pub)
    runner.run()
    assert len(pub.sent) == 1 and "a 3" in pub.sent[0]
    assert saved_seen(tmp_path, "a") == ["1", "2", "3"]


def test_new_entries_published_oldest_first_and_marked(tmp_path):
    pub = FakePublisher()
    config = make_config({"id": "a"})
    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["2", "1"])}, pub)
    runner.run()  # инициализация
    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["5", "4", "3", "2", "1"])}, pub)
    report = runner.run()
    assert [t.split("</b>")[0].split()[-1] for t in pub.sent] == ["3", "4", "5"]
    assert report.sources[0].new == 3 and report.sources[0].published == 3
    assert saved_seen(tmp_path, "a")[-3:] == ["3", "4", "5"]

    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["5", "4", "3", "2", "1"])}, pub)
    runner.run()
    assert len(pub.sent) == 3  # повторный запуск ничего не дублирует


def test_per_run_limit_defers_rest(tmp_path):
    pub = FakePublisher()
    config = make_config({"id": "a", "max_posts_per_run": 2})
    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["0"])}, pub)
    runner.run()
    feed = {"a": entries("a", ["5", "4", "3", "2", "1", "0"])}
    runner, _ = make_runner(tmp_path, config, feed, pub)
    report = runner.run()
    assert report.sources[0].deferred == 3
    assert ["1" in pub.sent[0], "2" in pub.sent[1]] == [True, True]
    for _ in range(2):
        runner, _ = make_runner(tmp_path, config, feed, pub)
        runner.run()
    assert len(pub.sent) == 5
    assert "a 5" in pub.sent[-1]


def test_telegram_failure_does_not_mark_entry(tmp_path):
    config = make_config({"id": "a"}, {"id": "b"})
    feeds = {"a": entries("a", ["1"]), "b": entries("b", ["1"])}
    runner, _ = make_runner(tmp_path, config, feeds, FakePublisher())
    runner.run()

    feeds = {"a": entries("a", ["3", "2", "1"]), "b": entries("b", ["2", "1"])}
    pub = FakePublisher(fail_on={"a 3"})
    runner, _ = make_runner(tmp_path, config, feeds, pub)
    report = runner.run()
    assert report.failed and "Forbidden" in report.telegram_error
    assert len(pub.sent) == 1 and "a 2" in pub.sent[0]
    assert saved_seen(tmp_path, "a") == ["1", "2"]  # "3" не помечена
    assert [s.source_id for s in report.sources] == ["a"]  # дальше не идём

    pub = FakePublisher()
    runner, _ = make_runner(tmp_path, config, feeds, pub)
    assert not runner.run().failed
    assert ["a 3" in pub.sent[0], "b 2" in pub.sent[1]] == [True, True]


def test_source_error_is_isolated(tmp_path):
    config = make_config({"id": "broken"}, {"id": "ok"})
    feeds = {"broken": ConnectionError("timeout"), "ok": entries("ok", ["1"])}
    runner, state = make_runner(tmp_path, config, feeds, FakePublisher())
    report = runner.run()
    assert "timeout" in report.sources[0].error
    assert report.sources[1].error is None and state.has_source("ok")
    assert not report.failed


def test_all_sources_failed_marks_run_failed(tmp_path):
    config = make_config({"id": "a"}, {"id": "b"})
    runner, _ = make_runner(tmp_path, config, {"a": RuntimeError("x"), "b": []}, FakePublisher())
    report = runner.run()
    assert report.failed
    assert "ни одной записи" in report.sources[1].error  # пустой результат — тоже ошибка


def test_window_prevents_old_entries_resurfacing(tmp_path):
    """Записи старше max_entries не рассматриваются, даже если их нет в state."""
    pub = FakePublisher()
    config = make_config({"id": "a", "max_entries": 3}, state_keep=5)
    versions = [str(v) for v in range(50, 0, -1)]
    runner, _ = make_runner(tmp_path, config, {"a": entries("a", versions)}, pub)
    runner.run()
    assert saved_seen(tmp_path, "a") == ["48", "49", "50"]
    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["51"] + versions)}, pub)
    runner.run()
    assert len(pub.sent) == 1 and "a 51" in pub.sent[0]


def test_dry_run_prints_and_keeps_state(tmp_path):
    config = make_config({"id": "a"})
    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["1"])}, FakePublisher())
    runner.run()
    before = (tmp_path / "state.json").read_text()

    runner, _ = make_runner(tmp_path, config, {"a": entries("a", ["2", "1"])}, None, dry_run=True)
    report = runner.run()
    assert "<b>a 2</b>" in runner.out.getvalue()
    assert report.sources[0].published == 1
    assert (tmp_path / "state.json").read_text() == before


def test_dry_run_preview_latest_on_fresh_state(tmp_path):
    config = make_config({"id": "a"}, {"id": "b"})
    feeds = {"a": entries("a", ["3", "2", "1"]), "b": entries("b", ["9"])}
    runner, _ = make_runner(tmp_path, config, feeds, None, dry_run=True, preview_latest=2)
    runner.run()
    out = runner.out.getvalue()
    assert out.index("<b>a 2</b>") < out.index("<b>a 3</b>")
    assert "<b>a 1</b>" not in out and "<b>b 9</b>" in out
    assert not (tmp_path / "state.json").exists()


def test_disabled_source_skipped_unless_selected(tmp_path):
    config = make_config({"id": "a", "enabled": False}, {"id": "b"})
    feeds = {"a": entries("a", ["1"]), "b": entries("b", ["1"])}
    runner, state = make_runner(tmp_path, config, feeds, FakePublisher())
    report = runner.run()
    assert [s.source_id for s in report.sources] == ["b"]
    report = runner.run(only={"a"})
    assert [s.source_id for s in report.sources] == ["a"] and state.has_source("a")


def test_enrich_failure_still_publishes(tmp_path):
    class BrokenEnrich(FakeParser):
        def enrich(self, entry):
            raise RuntimeError("blog down")

    pub = FakePublisher()
    config = make_config({"id": "a", "publish_latest_on_init": True})
    FakeParser.feeds = {"a": entries("a", ["1"])}
    runner = Runner(config, State(tmp_path / "state.json"), None, GeminiSummarizer(None), pub,
                    parser_factory=lambda s, h: BrokenEnrich(s, h), sleep=lambda _: None)
    runner.run()
    assert len(pub.sent) == 1


def test_live_run_requires_publisher(tmp_path):
    with pytest.raises(ValueError):
        Runner(make_config({"id": "a"}), State(tmp_path / "s.json"), None, GeminiSummarizer(None), None)
