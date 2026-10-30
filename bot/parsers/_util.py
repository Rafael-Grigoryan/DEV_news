"""Общие помощники парсеров: даты, версии, якоря, извлечение текста из HTML."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, date, datetime

from bs4 import Tag

MONTHS_EN = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
MONTHS_RU_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MDY_RE = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")
_DMY_RE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b")

# 2.1.314, v1.2, 3.50.0-0.3.pre, 3.14.0-150.0.dev, 1.0.0+build
VERSION_RE = re.compile(r"^v?(?P<version>\d+(?:\.\d+){1,3}(?:[-+][0-9A-Za-z][0-9A-Za-z.\-+]*)?)\b")

_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])")


def parse_date(text: str) -> date | None:
    """Дата из строки: 2026-10-29, October 29, 2026, Oct 29 2026, 29 October 2026."""
    if m := _ISO_DATE_RE.search(text):
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    if (m := _MDY_RE.search(text)) and m[1].lower() in MONTHS_EN:
        return _safe_date(int(m[3]), MONTHS_EN[m[1].lower()], int(m[2]))
    if (m := _DMY_RE.search(text)) and m[2].lower() in MONTHS_EN:
        return _safe_date(int(m[3]), MONTHS_EN[m[2].lower()], int(m[1]))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_datetime(text: str | None) -> datetime | None:
    """ISO 8601 (в т.ч. с Z на конце) -> aware datetime в UTC."""
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def date_to_datetime(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def ru_date(value: date) -> str:
    return f"{value.day} {MONTHS_RU_GENITIVE[value.month - 1]} {value.year}"


def is_prerelease(version: str) -> bool:
    """3.14.0-150.0.dev, 3.50.0-0.3.pre, 2.0.0-beta.1 — пре-релизы; 1.0.0+build — нет."""
    m = VERSION_RE.match(version.strip())
    return bool(m and "-" in m["version"])


def strip_md_links(text: str) -> str:
    """[text](url) и [text][ref] -> text."""
    return _MD_LINK_RE.sub(r"\1", text)


def github_slug(heading: str) -> str:
    """Якорь заголовка как у GitHub/Mintlify: '2.1.314' -> '21314', 'October 29, 2026' -> 'october-29-2026'."""
    text = strip_md_links(heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


# --- HTML -> текст ----------------------------------------------------------

BLOCK_TAGS = {"p", "li", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd"}
SKIP_INSIDE = {"nav", "aside", "figure", "script", "style", "noscript", "header", "footer", "button", "form"}
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,;:!?)])")


def blocks_to_text(tags: Iterable[Tag]) -> str:
    """Текст блочных элементов в markdown-lite: '- ' для пунктов, '## ' для заголовков."""
    lines: list[str] = []
    taken: set[int] = set()
    for el in tags:
        if el.name not in BLOCK_TAGS:
            continue
        if any(id(parent) in taken or parent.name in SKIP_INSIDE for parent in el.parents):
            continue
        taken.add(id(el))
        if el.name == "pre":
            code = el.get_text().strip("\n")
            if code.strip():
                lines.append(f"```\n{code}\n```")
            continue
        text = " ".join(el.get_text(" ", strip=True).split())
        text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
        if not text:
            continue
        if el.name == "li":
            text = f"- {text}"
        elif el.name[0] == "h":
            text = f"## {text}"
        elif _is_bold_only(el, text):
            text = f"**{text}**"
        # Блоки разделяем пустой строкой, подряд идущие пункты списка — переводом строки.
        if lines and not (text.startswith("- ") and lines[-1].startswith("- ")):
            lines.append("")
        lines.append(text)
    return "\n".join(lines)


def _is_bold_only(el: Tag, text: str) -> bool:
    bold = el.find(["b", "strong"])
    return bold is not None and " ".join(bold.get_text(" ", strip=True).split()) == text
