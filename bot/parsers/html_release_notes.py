"""HTML-страница с записями по датам (например, Claude Apps release notes в Help Center).

Каждая запись — заголовок `entry_heading` с датой и всё содержимое до следующего
заголовка из `stop_at`. Если у заголовка есть id, ссылка ведёт на его якорь.

Параметры источника:
  container_selector: article   # CSS-селектор области со статьёй
  entry_heading: h3             # тег заголовка записи
  stop_at: [h1, h2, h3]         # теги, на которых запись заканчивается
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from bot.models import Entry
from bot.parsers._util import blocks_to_text, date_to_datetime, github_slug, parse_date, ru_date
from bot.parsers.base import Parser


class HtmlReleaseNotesParser(Parser):
    type = "html_release_notes"

    def parse(self, payload: str) -> list[Entry]:
        soup = BeautifulSoup(payload, "html.parser")
        selector = self.source.opt("container_selector", "article")
        root = soup.select_one(selector) or soup.body or soup
        entry_tag = self.source.opt("entry_heading", "h3")
        stop_at = set(self.source.opt("stop_at", ["h1", "h2", "h3"])) | {entry_tag}

        all_tags = root.find_all(True)
        entries: list[Entry] = []
        seen: set[str] = set()
        for index, tag in enumerate(all_tags):
            if tag.name != entry_tag:
                continue
            heading = " ".join(tag.get_text(" ", strip=True).split())
            if not heading:
                continue
            body_tags = []
            for el in all_tags[index + 1 :]:
                if el.name in stop_at:
                    break
                body_tags.append(el)
            body = blocks_to_text(body_tags)
            if not body:
                continue

            section_date = parse_date(heading)
            if section_date is not None:
                entry_id = section_date.isoformat()
                title = f"{self.source.name} — {ru_date(section_date)}"
                published_at = date_to_datetime(section_date)
            else:
                entry_id = github_slug(heading)
                title = f"{self.source.name} — {heading}"
                published_at = None
            if entry_id in seen:
                continue
            seen.add(entry_id)

            anchor = tag.get("id")
            entries.append(
                self.make_entry(
                    entry_id=entry_id,
                    title=title,
                    raw_text=body,
                    url=f"{self.source.url}#{anchor}" if anchor else self.source.url,
                    published_at=published_at,
                )
            )
        return entries
