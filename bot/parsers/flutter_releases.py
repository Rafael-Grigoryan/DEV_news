"""Релизы Flutter.

GitHub Releases у flutter/flutter больше не ведутся (последняя запись — бета 2024 г.),
поэтому список версий берётся из официального JSON, который использует `flutter upgrade`
и страница архива SDK. Текст записи — секция `### [x.y.z]` из CHANGELOG.md
репозитория flutter/flutter. Версия попадает в бот только после появления в JSON,
так что заранее добавленные в CHANGELOG записи не опубликуются раньше релиза.

Для мажорных релизов (x.y.0) секция CHANGELOG — одна фраза со ссылкой на пост
в официальном блоге flutter.dev; при `enrich_from_blog: true` его текст подтягивается
в выжимку.

Параметры источника:
  url: .../releases_linux.json
  changelog_url: .../flutter/flutter/master/CHANGELOG.md
  include_prereleases: false     # true — ещё и канал beta
  enrich_from_blog: true
  blog_max_chars: 12000
  blog_content_selector: "article section.content"
  changelog_link_template, release_notes_link_template, prerelease_link_template
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace

from bs4 import BeautifulSoup

from bot.http import FetchError
from bot.models import Entry
from bot.parsers._util import VERSION_RE, blocks_to_text, github_slug, parse_datetime, strip_md_links
from bot.parsers.base import Parser
from bot.parsers.markdown_changelog import split_sections

log = logging.getLogger(__name__)

DEFAULT_CHANGELOG_LINK = "https://github.com/flutter/flutter/blob/master/CHANGELOG.md#{anchor}"
DEFAULT_RELEASE_NOTES_LINK = "https://docs.flutter.dev/release/release-notes/release-notes-{version}"
DEFAULT_PRERELEASE_LINK = "https://github.com/flutter/flutter/releases/tag/{version}"
# Тело поста в блоге flutter.dev; шапка с автором и меню «Share» лежат вне section.content.
DEFAULT_BLOG_SELECTOR = "article section.content"

_MAJOR_RE = re.compile(r"\d+\.\d+\.0")
_BLOG_LINK_RE = re.compile(r"https://(?:www\.)?flutter\.dev/blog/[\w\-/]+")


class FlutterReleasesParser(Parser):
    type = "flutter_releases"

    def fetch(self) -> list[Entry]:
        releases_json = self.http.get_text(self.source.url)
        changelog = ""
        if changelog_url := self.source.opt("changelog_url"):
            try:
                changelog = self.http.get_text(changelog_url)
            except FetchError as exc:
                log.warning("%s: CHANGELOG недоступен (%s), посты будут без деталей", self.source.id, exc)
        return self.parse(releases_json, changelog)

    def parse(self, payload: str, changelog: str = "") -> list[Entry]:
        data = json.loads(payload)
        channels = {"stable", "beta"} if self.source.include_prereleases else {"stable"}
        notes: dict[str, str] = {}
        for section in split_sections(changelog, 3):
            if m := VERSION_RE.match(strip_md_links(section.heading).strip()):
                notes.setdefault(m["version"], section.body.strip())

        releases = sorted(data.get("releases", []), key=lambda r: r.get("release_date", ""), reverse=True)
        entries: list[Entry] = []
        seen: set[str] = set()
        for release in releases:
            channel = release.get("channel")
            version = release.get("version", "")
            if channel not in channels or not version or version in seen:
                continue
            seen.add(version)
            stable = channel == "stable"
            body = notes.get(version) or f"Flutter {version} is available on the {channel} channel."
            if dart := release.get("dart_sdk_version"):
                body += f"\n\nDart SDK: {dart}"
            entries.append(
                self.make_entry(
                    entry_id=version,
                    title=f"{self.source.name} {version}" + ("" if stable else " (beta)"),
                    raw_text=body,
                    url=self._link(version, stable),
                    published_at=parse_datetime(release.get("release_date")),
                )
            )
        return entries

    def _link(self, version: str, stable: bool) -> str:
        if not stable:
            template = self.source.opt("prerelease_link_template", DEFAULT_PRERELEASE_LINK)
        elif _MAJOR_RE.fullmatch(version):
            template = self.source.opt("release_notes_link_template", DEFAULT_RELEASE_NOTES_LINK)
        else:
            template = self.source.opt("changelog_link_template", DEFAULT_CHANGELOG_LINK)
        return template.format(version=version, anchor=github_slug(version))

    def enrich(self, entry: Entry) -> Entry:
        if not self.source.opt("enrich_from_blog", True) or not _MAJOR_RE.fullmatch(entry.entry_id):
            return entry
        link = _BLOG_LINK_RE.search(entry.raw_text)
        if not link:
            return entry
        try:
            selector = self.source.opt("blog_content_selector", DEFAULT_BLOG_SELECTOR)
            article = article_text(self.http.get_text(link[0]), selector)
        except FetchError as exc:
            log.warning("%s: не удалось загрузить пост блога %s: %s", self.source.id, link[0], exc)
            return entry
        if not article:
            return entry
        article = article[: int(self.source.opt("blog_max_chars", 12000))]
        return replace(entry, raw_text=f"{entry.raw_text}\n\n## Release blog post\n\n{article}")


def article_text(html: str, selector: str = DEFAULT_BLOG_SELECTOR) -> str:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(selector) or soup.find("article") or soup.body or soup
    return blocks_to_text(root.find_all(True))
