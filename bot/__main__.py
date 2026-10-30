"""CLI: python -m bot [--dry-run] [--preview-latest N] [--only ID[,ID]]"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from bot.config import ConfigError, load_config, load_dotenv
from bot.http import HttpClient
from bot.runner import Runner
from bot.state import State, StateError
from bot.summarizer import GeminiSummarizer, parse_models
from bot.telegram import TelegramPublisher

log = logging.getLogger("bot")


class _Formatter(logging.Formatter):
    """В GitHub Actions предупреждения и ошибки становятся аннотациями (::warning::)."""

    def __init__(self, github: bool):
        super().__init__("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
        self.github = github

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self.github and record.levelno >= logging.WARNING:
            kind = "error" if record.levelno >= logging.ERROR else "warning"
            return f"::{kind}::" + text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return text


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m bot", description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="ничего не отправлять в Telegram и не менять state.json, только печатать посты")
    parser.add_argument("--preview-latest", type=int, default=0, metavar="N",
                        help="(только с --dry-run) показать N последних записей каждого источника как посты")
    parser.add_argument("--only", default="", metavar="ID[,ID]",
                        help="проверить только эти источники (можно и отключённые)")
    parser.add_argument("--config", default="sources.yaml", help="путь к sources.yaml")
    parser.add_argument("--state", default="state.json", help="путь к state.json")
    parser.add_argument("-v", "--verbose", action="store_true", help="подробный лог")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_Formatter(github=os.environ.get("GITHUB_ACTIONS") == "true"))
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, handlers=[handler])
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    load_dotenv(Path.cwd() / ".env")

    if args.preview_latest and not args.dry_run:
        log.error("--preview-latest работает только вместе с --dry-run")
        return 2
    try:
        config = load_config(args.config)
        state = State(args.state, keep=config.settings.state_keep)
    except (ConfigError, StateError) as exc:
        log.error("%s", exc)
        return 2

    only = {part.strip() for part in args.only.split(",") if part.strip()} or None
    if only and (unknown := only - {s.id for s in config.sources}):
        log.error("неизвестные источники в --only: %s", ", ".join(sorted(unknown)))
        return 2

    settings = config.settings
    publisher = None
    if not args.dry_run:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            log.error("TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID не заданы (для проверки без отправки: --dry-run)")
            return 1
        publisher = TelegramPublisher(
            token, chat_id,
            disable_web_page_preview=settings.disable_web_page_preview,
            timeout=settings.request_timeout,
        )

    summarizer = GeminiSummarizer(
        os.environ.get("GEMINI_API_KEY", "").strip(),
        parse_models(os.environ.get("GEMINI_MODEL")),
        fallback_max_chars=settings.fallback_max_chars,
    )
    http = HttpClient(timeout=settings.request_timeout, github_token=os.environ.get("GITHUB_TOKEN") or None)

    mode = "DRY RUN" if args.dry_run else "боевой запуск"
    log.info("Старт: %s, модели Gemini: %s, источников в конфиге: %d",
             mode, " → ".join(summarizer.models), len(config.sources))
    runner = Runner(config, state, http, summarizer, publisher,
                    dry_run=args.dry_run, preview_latest=args.preview_latest)
    report = runner.run(only=only)

    log.info("Итог:")
    for sr in report.sources:
        if sr.error:
            log.info("  %-12s ОШИБКА: %s", sr.source_id, sr.error)
        elif sr.initialized and not args.preview_latest:
            log.info("  %-12s инициализирован (%d записей запомнено), постов: %d",
                     sr.source_id, sr.fetched, sr.published)
        else:
            verb = "показано" if args.dry_run else "опубликовано"
            deferred = f", отложено: {sr.deferred}" if sr.deferred else ""
            log.info("  %-12s записей: %d, новых: %d, %s: %d%s",
                     sr.source_id, sr.fetched, sr.new, verb, sr.published, deferred)
    if report.failed:
        log.error("Прогон завершился с ошибкой: %s",
                  report.telegram_error or "ни один источник не удалось получить")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
