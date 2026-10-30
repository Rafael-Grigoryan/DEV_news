"""Сборка поста в Telegram HTML и обрезка под лимит 4096 символов.

Модель и фоллбэк отдают пункты в markdown-lite: `code` и **bold**. Здесь весь
текст экранируется, и только эти две конструкции превращаются в теги, поэтому
в сообщение никогда не попадёт посторонний или незакрытый HTML.
"""

from __future__ import annotations

import re
from html import escape

from bot.config import SourceConfig
from bot.models import Entry, Summary

TELEGRAM_LIMIT = 4096
FALLBACK_NOTE = "⚠️ <i>Автоперевод недоступен, оригинальный текст:</i>"
MORE_MARKER = "• …"

_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")


def tg_len(text: str) -> int:
    """Длина в UTF-16 code units — так Telegram считает лимит; эмодзи занимают 2."""
    return len(text.encode("utf-16-le")) // 2


def inline_to_html(text: str) -> str:
    parts = _CODE_RE.split(text)
    out = []
    for index, part in enumerate(parts):
        if index % 2:
            out.append(f"<code>{escape(part, quote=False)}</code>")
        else:
            out.append(_BOLD_RE.sub(r"<b>\1</b>", escape(part, quote=False)))
    return "".join(out)


def format_post(source: SourceConfig, entry: Entry, summary: Summary, limit: int = TELEGRAM_LIMIT) -> str:
    header = f"{source.emoji} <b>{escape(entry.title, quote=False)}</b>".strip()
    footer = f'🔗 <a href="{escape(entry.url, quote=True)}">{escape(source.link_text, quote=False)}</a>'
    if source.hashtag:
        footer += "\n" + escape(source.hashtag, quote=False)
    note = "" if summary.translated else FALLBACK_NOTE

    def build(bullets: list[str]) -> str:
        blocks = [header]
        if note:
            blocks.append(note)
        if bullets:
            blocks.append("\n".join(bullets))
        blocks.append(footer)
        return "\n\n".join(blocks)

    items = [item for item in summary.items if item.strip()]
    bullets = [f"• {inline_to_html(item)}" for item in items]
    text = build(bullets)
    if tg_len(text) <= limit:
        return text

    # Не влезает: оставляем столько целых пунктов, сколько помещается, плюс «• …».
    kept: list[str] = []
    for bullet in bullets:
        if tg_len(build(kept + [bullet, MORE_MARKER])) > limit:
            break
        kept.append(bullet)
    if not kept:
        budget = limit - tg_len(build([MORE_MARKER])) - 1
        kept = [_fit_bullet(items[0], budget)]
    return build(kept + [MORE_MARKER])


def _fit_bullet(item: str, budget: int) -> str:
    """Один пункт длиннее лимита: укорачиваем исходный текст по границе слова."""
    length = len(item)
    while length > 0:
        cut = item[:length].rsplit(" ", 1)[0] if " " in item[:length] else item[:length]
        bullet = f"• {inline_to_html(cut.rstrip())}…"
        if tg_len(bullet) <= budget:
            return bullet
        length = int(length * 0.9)
    return "• …"
