from bot.formatter import FALLBACK_NOTE, TELEGRAM_LIMIT, format_post, inline_to_html, tg_len
from bot.models import Entry, Summary
from tests.conftest import make_source

SOURCE = make_source(id="claude_code", name="Claude Code", emoji="⌨️", hashtag="#ClaudeCode")
ENTRY = Entry(
    source_id="claude_code",
    entry_id="2.1.314",
    title="Claude Code 2.1.314",
    raw_text="",
    url="https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21314",
)


def test_post_layout():
    text = format_post(SOURCE, ENTRY, Summary(["Первый пункт", "Второй пункт"], translated=True))
    assert text == (
        "⌨️ <b>Claude Code 2.1.314</b>\n"
        "\n"
        "• Первый пункт\n"
        "• Второй пункт\n"
        "\n"
        '🔗 <a href="https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21314">Полный changelog</a>\n'
        "#ClaudeCode"
    )


def test_escaping_and_inline_code():
    assert inline_to_html("Флаг `--x <y>` & a < b") == "Флаг <code>--x &lt;y&gt;</code> &amp; a &lt; b"
    assert inline_to_html("**Breaking:** удалён `foo()`") == "<b>Breaking:</b> удалён <code>foo()</code>"
    # незакрытая обратная кавычка и звёздочки остаются текстом
    assert inline_to_html("a ` b ** c") == "a ` b ** c"
    assert inline_to_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_title_and_url_are_escaped():
    entry = Entry("s", "1", "A <b> & B", "", 'https://x.test/?a=1&b="2"')
    text = format_post(SOURCE, entry, Summary(["x"], translated=True))
    assert "<b>A &lt;b&gt; &amp; B</b>" in text
    assert 'href="https://x.test/?a=1&amp;b=&quot;2&quot;"' in text


def test_fallback_note():
    text = format_post(SOURCE, ENTRY, Summary(["Added `x`"], translated=False))
    assert FALLBACK_NOTE in text
    assert text.index(FALLBACK_NOTE) < text.index("• Added <code>x</code>")


def test_truncation_keeps_whole_bullets_and_footer():
    items = [(f"Пункт номер {i}: " + "очень длинное описание изменения " * 6).strip() for i in range(100)]
    text = format_post(SOURCE, ENTRY, Summary(items, translated=True))
    assert tg_len(text) <= TELEGRAM_LIMIT
    assert text.endswith("Полный changelog</a>\n#ClaudeCode")
    body = text.split("\n\n")[1].split("\n")
    assert body[-1] == "• …"
    kept = body[:-1]
    assert len(kept) > 5
    assert kept == [f"• {item}" for item in items[: len(kept)]]


def test_single_huge_bullet_is_shortened():
    text = format_post(SOURCE, ENTRY, Summary(["слово " * 2000], translated=True))
    assert tg_len(text) <= TELEGRAM_LIMIT
    assert "…" in text
    assert text.endswith("#ClaudeCode")


def test_emoji_counted_as_two_utf16_units():
    assert tg_len("🔗") == 2
    items = ["🔥" * 300] * 20  # 600 UTF-16 единиц на пункт, хотя len() == 300
    text = format_post(SOURCE, ENTRY, Summary(items, translated=True))
    assert tg_len(text) <= TELEGRAM_LIMIT
