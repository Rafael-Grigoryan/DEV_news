from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Entry:
    """Одна запись changelog'а: версия, дата или релиз."""

    source_id: str
    entry_id: str  # стабильный ключ для дедупликации: версия, ISO-дата, tag, guid
    title: str  # заголовок поста без эмодзи, например "Claude Code 2.1.314"
    raw_text: str  # исходный текст записи (markdown или plain text)
    url: str  # ссылка прямо на запись (с якорем, если возможно)
    published_at: datetime | None = None


@dataclass(frozen=True)
class Summary:
    """Текст для тела поста: пункты в markdown-lite (`code`, **bold**)."""

    items: list[str]
    translated: bool  # False — это оригинальный текст (фоллбэк без Gemini)
