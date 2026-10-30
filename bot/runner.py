"""Один прогон: опросить источники, найти новые записи, сделать выжимки, опубликовать."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TextIO

from bot.config import Config, SourceConfig
from bot.formatter import format_post, tg_len
from bot.http import HttpClient
from bot.models import Entry
from bot.parsers import Parser, create_parser
from bot.state import State
from bot.summarizer import GeminiSummarizer
from bot.telegram import TelegramError, TelegramPublisher

log = logging.getLogger(__name__)


@dataclass
class SourceReport:
    source_id: str
    fetched: int = 0
    new: int = 0
    published: int = 0
    deferred: int = 0
    initialized: bool = False
    error: str | None = None


@dataclass
class RunReport:
    sources: list[SourceReport] = field(default_factory=list)
    telegram_error: str | None = None

    @property
    def failed(self) -> bool:
        """Прогон неуспешен, если Telegram недоступен или не ответил ни один источник."""
        all_sources_failed = bool(self.sources) and all(s.error for s in self.sources)
        return bool(self.telegram_error) or all_sources_failed


class Runner:
    def __init__(
        self,
        config: Config,
        state: State,
        http: HttpClient,
        summarizer: GeminiSummarizer,
        publisher: TelegramPublisher | None,
        *,
        dry_run: bool = False,
        preview_latest: int = 0,
        parser_factory: Callable[[SourceConfig, HttpClient], Parser] = create_parser,
        out: TextIO = sys.stdout,
        sleep=time.sleep,
    ):
        if not dry_run and publisher is None:
            raise ValueError("для боевого запуска нужен publisher")
        self.config = config
        self.state = state
        self.http = http
        self.summarizer = summarizer
        self.publisher = publisher
        self.dry_run = dry_run
        self.preview_latest = preview_latest
        self.parser_factory = parser_factory
        self.out = out
        self._sleep = sleep
        self._posted_any = False

    def run(self, only: set[str] | None = None) -> RunReport:
        report = RunReport()
        for source in self.config.sources:
            if only is not None and source.id not in only:
                continue
            if not source.enabled and only is None:
                log.info("[%s] отключён в sources.yaml, пропускаю", source.id)
                continue
            source_report = SourceReport(source.id)
            report.sources.append(source_report)
            self._process(source, source_report, report)
            if report.telegram_error:
                log.error("Telegram недоступен, остальные источники пропущены до следующего запуска")
                break
        return report

    def _process(self, source: SourceConfig, sr: SourceReport, report: RunReport) -> None:
        parser = self.parser_factory(source, self.http)
        try:
            entries = parser.fetch()
            if not entries:
                raise ValueError("не найдено ни одной записи — возможно, изменилась структура страницы")
        except Exception as exc:  # noqa: BLE001 — сбой одного источника не ломает остальные
            sr.error = f"{type(exc).__name__}: {exc}"
            log.error("[%s] ошибка получения %s: %s", source.id, source.url, sr.error)
            return
        entries = entries[: source.max_entries]
        sr.fetched = len(entries)

        for entry in self._select(source, entries, sr):
            if not self._publish(source, parser, entry, sr, report):
                return

    def _select(self, source: SourceConfig, entries: list[Entry], sr: SourceReport) -> list[Entry]:
        """Записи к публикации, от старых к новым. `entries` — от новых к старым."""
        if self.preview_latest:
            log.info("[%s] preview: беру %d последних записей", source.id, self.preview_latest)
            return list(reversed(entries[: self.preview_latest]))

        if not self.state.has_source(source.id):
            ids = [e.entry_id for e in reversed(entries)]
            sr.initialized = True
            if source.publish_latest_on_init:
                self.state.initialize(source.id, ids[:-1])
                candidates = [entries[0]]
            else:
                self.state.initialize(source.id, ids)
                candidates = []
            log.info(
                "[%s] первый запуск: запомнил %d записей (последняя: %s)%s",
                source.id, len(entries), entries[0].entry_id,
                ", публикую последнюю" if candidates else ", ничего не публикую",
            )
            self._save_state()
            return candidates

        seen = self.state.seen_ids(source.id)
        new = [e for e in reversed(entries) if e.entry_id not in seen]
        sr.new = len(new)
        limit = source.max_posts_per_run
        if len(new) > limit:
            sr.deferred = len(new) - limit
            log.info("[%s] новых записей %d, публикую %d старейших, остальные в следующих запусках",
                     source.id, len(new), limit)
        log.info("[%s] записей: %d, новых: %d%s", source.id, len(entries), len(new),
                 f" ({', '.join(e.entry_id for e in new)})" if new else "")
        return new[:limit]

    def _publish(self, source: SourceConfig, parser: Parser, entry: Entry, sr: SourceReport,
                 report: RunReport) -> bool:
        try:
            entry = parser.enrich(entry)
        except Exception as exc:  # noqa: BLE001 — без обогащения пост всё равно можно сделать
            log.warning("[%s] не удалось дополнить %s: %s", source.id, entry.entry_id, exc)
        summary = self.summarizer.summarize(entry, source)
        text = format_post(source, entry, summary)

        if self.dry_run:
            mode = "перевод Gemini" if summary.translated else "оригинал, без Gemini"
            print(f"\n{'=' * 20} [{source.id}] {entry.entry_id} · {tg_len(text)} симв. · {mode} {'=' * 20}",
                  file=self.out)
            print(text, file=self.out, flush=True)
            sr.published += 1
            return True

        if self._posted_any:
            self._sleep(self.config.settings.post_delay_seconds)
        try:
            self.publisher.send(text)
        except TelegramError as exc:
            report.telegram_error = str(exc)
            log.error("[%s] не удалось отправить %s в Telegram: %s", source.id, entry.entry_id, exc)
            return False
        self._posted_any = True
        # Помечаем только после успешной отправки и сразу пишем на диск.
        self.state.mark_seen(source.id, entry.entry_id)
        self._save_state()
        sr.published += 1
        log.info("[%s] опубликовано: %s", source.id, entry.title)
        return True

    def _save_state(self) -> None:
        if not self.dry_run and not self.preview_latest:
            self.state.save()
