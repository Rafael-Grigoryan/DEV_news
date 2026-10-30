from datetime import UTC, datetime

from bot.parsers.markdown_changelog import MarkdownChangelogParser, split_sections
from tests.conftest import make_source, read_fixture


def parse(fixture_or_text: str, **source_kwargs):
    text = read_fixture(fixture_or_text) if fixture_or_text.endswith(".md") else fixture_or_text
    return MarkdownChangelogParser(make_source(**source_kwargs), http=None).parse(text)


def test_claude_code_versions():
    entries = parse(
        "claude_code_CHANGELOG.md",
        name="Claude Code",
        link_template="https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#{anchor}",
    )
    assert [e.entry_id for e in entries] == ["2.1.314", "2.1.312", "2.1.311"]
    first = entries[0]
    assert first.title == "Claude Code 2.1.314"
    assert first.url == "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21314"
    assert first.raw_text.startswith("- Added `permissions.blockWritesOutsideWorkingDirectories`")
    assert "## 2.1.312" not in first.raw_text
    assert "Fixed Esc on a command's panel" in first.raw_text  # последняя строка секции


def test_dart_stable_branch():
    entries = parse("dart_stable_CHANGELOG.md", name="Dart")
    assert [e.entry_id for e in entries] == ["3.13.7", "3.13.6", "3.13.5", "3.13.4"]
    assert entries[0].published_at == datetime(2026, 10, 22, tzinfo=UTC)
    assert "Released on" not in entries[0].raw_text
    assert entries[0].raw_text.startswith("This is a patch release that:")


def test_dart_main_skips_unreleased_sections():
    entries = parse("dart_main_CHANGELOG.md", name="Dart")
    # 3.15.0 и 3.14.0 помечены "Released on: Unreleased"
    assert [e.entry_id for e in entries] == ["3.13.3", "3.13.2", "3.13.1"]


def test_unreleased_kept_when_disabled():
    entries = parse("dart_main_CHANGELOG.md", name="Dart", skip_unreleased=False)
    assert [e.entry_id for e in entries][:2] == ["3.15.0", "3.14.0"]


PRERELEASE_MD = """\
## 3.15.0-wip

- work in progress

## 3.14.0-150.0.dev

- dev build

## 3.13.0

- stable
"""


def test_prereleases_filtered_by_default():
    assert [e.entry_id for e in parse(PRERELEASE_MD)] == ["3.13.0"]


def test_prereleases_included_on_flag_but_wip_still_skipped():
    entries = parse(PRERELEASE_MD, include_prereleases=True)
    assert [e.entry_id for e in entries] == ["3.14.0-150.0.dev", "3.13.0"]


def test_headings_inside_code_fences_are_ignored():
    text = "## 1.1.0\n\n```bash\n# comment\n## 9.9.9\n```\n- after code\n\n## 1.0.0\n- old\n"
    entries = parse(text)
    assert [e.entry_id for e in entries] == ["1.1.0", "1.0.0"]
    assert "- after code" in entries[0].raw_text


def test_non_version_headings_are_skipped():
    text = "# Changelog\n\n## Unreleased\n- x\n\n## 2.0.0\n- y\n"
    assert [e.entry_id for e in parse(text)] == ["2.0.0"]


def test_claude_api_release_notes_by_date():
    entries = parse(
        "claude_api_release_notes.md",
        name="Claude API",
        heading_level=3,
        id_kind="date",
        link_template="https://platform.claude.com/docs/en/release-notes/overview#{anchor}",
    )
    assert len(entries) == 8
    first = entries[0]
    assert first.entry_id == "2026-10-29"
    assert first.title == "Claude API — 29 октября 2026"
    assert first.url == "https://platform.claude.com/docs/en/release-notes/overview#october-29-2026"
    assert "Usage and Cost Analytics API" in first.raw_text
    # фронтматтер и врезка <Tip> до первой даты не попадают ни в одну запись
    assert all("<Tip>" not in e.raw_text and "title:" not in e.raw_text for e in entries)
    assert entries[-1].entry_id == "2026-10-14"


def test_split_sections_stops_at_higher_level():
    sections = split_sections("## Flutter 3.47 Changes\n### [3.47.1](x)\n- a\n## Flutter 3.44 Changes\n- b\n", 3)
    assert [(s.heading, s.body) for s in sections] == [("[3.47.1](x)", "- a")]
