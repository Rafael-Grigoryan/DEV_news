"""GitHub Releases через REST API.

Параметры источника:
  url: https://api.github.com/repos/OWNER/REPO/releases?per_page=30
  include_prereleases: false   # флаг prerelease И суффикс версии в теге (-beta, .pre)
  title_from: tag              # tag | name — что показывать в заголовке поста

В Actions запросы идут с GITHUB_TOKEN (лимит 1000/час на репозиторий вместо 60/час на IP).
"""

from __future__ import annotations

import json

from bot.models import Entry
from bot.parsers._util import is_prerelease, parse_datetime
from bot.parsers.base import Parser


class GithubReleasesParser(Parser):
    type = "github_releases"

    def fetch(self) -> list[Entry]:
        resp = self.http.get(self.source.url, headers={"Accept": "application/vnd.github+json"})
        return self.parse(resp.text)

    def parse(self, payload: str) -> list[Entry]:
        title_from = self.source.opt("title_from", "tag")
        entries: list[Entry] = []
        for release in json.loads(payload):
            tag = release.get("tag_name") or ""
            if release.get("draft") or not tag:
                continue
            # Проверяем и флаг, и сам тег: у flutter/flutter беты помечены prerelease=false.
            if not self.source.include_prereleases and (release.get("prerelease") or is_prerelease(tag)):
                continue
            label = release.get("name") if title_from == "name" and release.get("name") else tag
            if label[:1] == "v" and label[1:2].isdigit():
                label = label[1:]
            entries.append(
                self.make_entry(
                    entry_id=tag,
                    title=f"{self.source.name} {label}",
                    raw_text=(release.get("body") or "").strip() or f"Release {tag}",
                    url=release.get("html_url") or self.source.url,
                    published_at=parse_datetime(release.get("published_at") or release.get("created_at")),
                )
            )
        entries.sort(key=lambda e: e.published_at.timestamp() if e.published_at else 0, reverse=True)
        return entries
