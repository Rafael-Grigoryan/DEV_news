import re

from bot.parsers.html_release_notes import HtmlReleaseNotesParser
from tests.conftest import make_source, read_fixture

APPS_URL = "https://support.claude.com/en/articles/12138966-release-notes"


def parse_apps():
    source = make_source(name="Claude Apps", type="html_release_notes", url=APPS_URL)
    return HtmlReleaseNotesParser(source, http=None).parse(read_fixture("claude_apps_release_notes.html"))


def test_entries_by_date_newest_first():
    entries = parse_apps()
    html = read_fixture("claude_apps_release_notes.html")
    assert len(entries) == len(re.findall(r"<h3", html))
    assert [e.entry_id for e in entries[:3]] == ["2026-10-21", "2026-10-07", "2026-09-28"]
    assert entries[0].title == "Claude Apps — 21 октября 2026"


def test_anchor_links():
    first = parse_apps()[0]
    assert first.url == f"{APPS_URL}#h_fdbb85f303"


def test_body_contains_only_own_items():
    entries = parse_apps()
    duet, october_7 = entries[0], entries[1]
    assert duet.raw_text.startswith("**Claude Duet research preview for Pro and Max plans**")
    assert "Claude Duet, a new app where Claude works as a proactive agent" in duet.raw_text
    assert "Haiku" not in duet.raw_text
    # несколько анонсов под одной датой — одна запись
    assert "**Claude Haiku 5.5 launch**" in october_7.raw_text
    assert "**Monthly API credits for Max and Team plans**" in october_7.raw_text
    # заголовок месяца (h2) завершает запись и в текст не попадает
    assert "September 2026" not in october_7.raw_text


def test_heading_without_date_uses_slug():
    html = '<article><h3 id="x1">Spring update</h3><p>Something new</p></article>'
    source = make_source(name="Demo", type="html_release_notes", url="https://example.com/notes")
    [entry] = HtmlReleaseNotesParser(source, http=None).parse(html)
    assert entry.entry_id == "spring-update"
    assert entry.url == "https://example.com/notes#x1"
    assert entry.raw_text == "Something new"
