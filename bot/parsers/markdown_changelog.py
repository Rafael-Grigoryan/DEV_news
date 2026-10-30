"""Markdown-changelog с секциями по версиям или датам.

Подходит для CHANGELOG.md на GitHub (Claude Code, Dart) и для release notes,
которые отдаются как markdown (Claude Platform: `.../overview.md`).

Параметры источника:
  heading_level: 2         # уровень заголовков секций (## = 2, ### = 3)
  id_kind: version         # version | date — что в заголовке секции
  link_template: ...#{anchor}   # ссылка на запись; {anchor}, {id} — подстановки
  skip_unreleased: true    # пропускать «Unreleased», «-wip», «Released on: TBD»
  include_prereleases: false
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bot.models import Entry
from bot.parsers._util import (
    VERSION_RE,
    date_to_datetime,
    github_slug,
    is_prerelease,
    parse_date,
    ru_date,
    strip_md_links,
)
from bot.parsers.base import Parser

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RELEASED_ON_RE = re.compile(r"^\s*\*\*Released on:?\*\*:?\s*(?P<value>.*?)\s*$", re.I | re.M)
_UNRELEASED_RE = re.compile(r"unreleased|not yet released|\bwip\b|-wip\b|\btbd\b|\btba\b", re.I)


@dataclass
class Section:
    heading: str
    lines: list[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        return "\n".join(self.lines).strip("\n")


def split_sections(markdown: str, level: int) -> list[Section]:
    """Секции под заголовками ровно уровня `level`.

    Секция заканчивается на следующем заголовке того же или более высокого уровня.
    Строки внутри ``` / ~~~ блоков заголовками не считаются.
    """
    sections: list[Section] = []
    current: Section | None = None
    fence: str | None = None
    for line in markdown.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            if fence is None:
                fence = stripped[:3]
            elif stripped.startswith(fence):
                fence = None
        elif fence is None and (m := _HEADING_RE.match(line)):
            heading_level = len(m[1])
            if heading_level <= level:
                if current is not None:
                    sections.append(current)
                current = Section(m[2]) if heading_level == level else None
                continue
        if current is not None:
            current.lines.append(line)
    if current is not None:
        sections.append(current)
    return sections


class MarkdownChangelogParser(Parser):
    type = "markdown_changelog"

    def parse(self, payload: str) -> list[Entry]:
        level = int(self.source.opt("heading_level", 2))
        id_kind = self.source.opt("id_kind", "version")
        if id_kind not in ("version", "date"):
            raise ValueError(f"{self.source.id}: id_kind должен быть version или date")
        skip_unreleased = bool(self.source.opt("skip_unreleased", True))
        link_template = self.source.opt("link_template") or self.source.url + "#{anchor}"

        entries: list[Entry] = []
        seen: set[str] = set()
        for section in split_sections(payload, level):
            heading = strip_md_links(section.heading).strip()
            body = section.body
            published_at = None

            released = _RELEASED_ON_RE.search(body)
            if released:
                released_date = parse_date(released["value"])
                if released_date is None and skip_unreleased:
                    continue  # "Released on: Unreleased" / TBD
                published_at = date_to_datetime(released_date) if released_date else None
                body = _RELEASED_ON_RE.sub("", body, count=1).strip("\n")
            if skip_unreleased and _UNRELEASED_RE.search(heading):
                continue

            if id_kind == "version":
                m = VERSION_RE.match(heading)
                if not m:
                    continue
                entry_id = m["version"]
                if is_prerelease(entry_id) and not self.source.include_prereleases:
                    continue
                title = f"{self.source.name} {entry_id}"
            else:
                section_date = parse_date(heading)
                if section_date is None:
                    continue
                entry_id = section_date.isoformat()
                title = f"{self.source.name} — {ru_date(section_date)}"
                published_at = published_at or date_to_datetime(section_date)

            if entry_id in seen:
                continue
            seen.add(entry_id)
            entries.append(
                self.make_entry(
                    entry_id=entry_id,
                    title=title,
                    raw_text=body.strip(),
                    url=link_template.format(anchor=github_slug(heading), id=entry_id),
                    published_at=published_at,
                )
            )
        return entries
