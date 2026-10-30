"""RSS 2.0 и Atom-ленты.

Параметры источника:
  title_regex: "Flutter \\d"   # необязательно: брать только элементы с подходящим заголовком
  title_prefix: false          # true — "Имя источника: заголовок элемента"
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from bot.models import Entry
from bot.parsers._util import blocks_to_text, parse_datetime
from bot.parsers.base import Parser

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT_ENCODED = "{http://purl.org/rss/1.0/modules/content/}encoded"


class RssParser(Parser):
    type = "rss"

    def fetch(self) -> list[Entry]:
        return self.parse(self.http.get_bytes(self.source.url))

    def parse(self, payload: str | bytes) -> list[Entry]:
        root = ET.fromstring(payload.encode("utf-8") if isinstance(payload, str) else payload)
        items = root.iter(f"{ATOM}entry") if root.tag == f"{ATOM}feed" else root.iter("item")
        title_re = re.compile(self.source.opt("title_regex")) if self.source.opt("title_regex") else None

        entries: list[Entry] = []
        seen: set[str] = set()
        for item in items:
            parsed = _parse_atom(item) if item.tag == f"{ATOM}entry" else _parse_rss(item)
            title, link, entry_id, published_at, content = parsed
            if not entry_id or entry_id in seen or (title_re and not title_re.search(title)):
                continue
            seen.add(entry_id)
            entries.append(
                self.make_entry(
                    entry_id=entry_id,
                    title=f"{self.source.name}: {title}" if self.source.opt("title_prefix") else title,
                    raw_text=_html_to_text(content) or title,
                    url=link or self.source.url,
                    published_at=published_at,
                )
            )
        if all(e.published_at for e in entries):
            entries.sort(key=lambda e: e.published_at, reverse=True)
        return entries


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _parse_rss(item: ET.Element):
    link = _text(item.find("link"))
    guid = _text(item.find("guid")) or link
    published_at = None
    if pub_date := _text(item.find("pubDate")):
        try:
            published_at = parsedate_to_datetime(pub_date)
        except (TypeError, ValueError):
            pass
    content = _text(item.find(CONTENT_ENCODED)) or _text(item.find("description"))
    return _text(item.find("title")), link, guid, published_at, content


def _parse_atom(item: ET.Element):
    link = ""
    for el in item.findall(f"{ATOM}link"):
        if el.get("rel", "alternate") == "alternate":
            link = el.get("href", "")
            break
    entry_id = _text(item.find(f"{ATOM}id")) or link
    published_at = parse_datetime(_text(item.find(f"{ATOM}published")) or _text(item.find(f"{ATOM}updated")))
    content = _text(item.find(f"{ATOM}content")) or _text(item.find(f"{ATOM}summary"))
    return _text(item.find(f"{ATOM}title")), link, entry_id, published_at, content


def _html_to_text(content: str) -> str:
    if "<" not in content:
        return content.strip()
    soup = BeautifulSoup(content, "html.parser")
    return blocks_to_text(soup.find_all(True)) or soup.get_text(" ", strip=True)
