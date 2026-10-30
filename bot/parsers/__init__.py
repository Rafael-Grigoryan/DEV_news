"""Реестр парсеров: значение `type` в sources.yaml -> класс парсера.

Новый тип: создайте файл с подклассом `Parser` (атрибут `type` + метод `parse`
или `fetch`), импортируйте его здесь и добавьте в кортеж ниже.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bot.parsers.base import Parser
from bot.parsers.flutter_releases import FlutterReleasesParser
from bot.parsers.github_releases import GithubReleasesParser
from bot.parsers.html_release_notes import HtmlReleaseNotesParser
from bot.parsers.markdown_changelog import MarkdownChangelogParser
from bot.parsers.rss import RssParser

if TYPE_CHECKING:
    from bot.config import SourceConfig
    from bot.http import HttpClient

PARSERS: dict[str, type[Parser]] = {
    cls.type: cls
    for cls in (
        MarkdownChangelogParser,
        HtmlReleaseNotesParser,
        FlutterReleasesParser,
        GithubReleasesParser,
        RssParser,
    )
}


def create_parser(source: SourceConfig, http: HttpClient) -> Parser:
    return PARSERS[source.type](source, http)
