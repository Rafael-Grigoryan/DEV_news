import json

from bot.http import FetchError
from bot.parsers.flutter_releases import FlutterReleasesParser
from tests.conftest import FakeHttp, make_source, read_fixture

RELEASES_URL = "https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json"
CHANGELOG_URL = "https://raw.githubusercontent.com/flutter/flutter/master/CHANGELOG.md"
BLOG_URL = "https://flutter.dev/blog/whats-new-in-flutter-3-47"


def make_parser(http=None, **kwargs):
    source = make_source(
        name="Flutter", type="flutter_releases", url=RELEASES_URL, changelog_url=CHANGELOG_URL, **kwargs
    )
    return FlutterReleasesParser(source, http or FakeHttp())


def releases_with_major():
    """Реальный JSON + запись 3.47.0 (она старше 20 релизов, попавших в фикстуру)."""
    data = json.loads(read_fixture("flutter_releases_linux.json"))
    data["releases"].append(
        {"version": "3.47.0", "channel": "stable", "release_date": "2026-08-12T17:00:00.000000Z",
         "dart_sdk_version": "3.13.0", "hash": "x"}
    )
    return json.dumps(data)


def test_stable_only_newest_first():
    entries = make_parser().parse(read_fixture("flutter_releases_linux.json"), read_fixture("flutter_CHANGELOG.md"))
    ids = [e.entry_id for e in entries]
    assert ids[:3] == ["3.47.9", "3.47.8", "3.47.7"]
    assert all(".pre" not in i for i in ids)


def test_changelog_text_and_links():
    entries = make_parser().parse(read_fixture("flutter_releases_linux.json"), read_fixture("flutter_CHANGELOG.md"))
    by_id = {e.entry_id: e for e in entries}
    assert "MAX_PATH" in by_id["3.47.9"].raw_text
    assert "Security advisory" in by_id["3.47.8"].raw_text
    assert "Dart SDK: 3.13.7" in by_id["3.47.9"].raw_text
    assert by_id["3.47.9"].url == "https://github.com/flutter/flutter/blob/master/CHANGELOG.md#3479"
    assert by_id["3.47.9"].published_at.year == 2026


def test_beta_channel_with_include_prereleases():
    parser = make_parser(include_prereleases=True)
    entries = parser.parse(read_fixture("flutter_releases_linux.json"), read_fixture("flutter_CHANGELOG.md"))
    beta = next(e for e in entries if e.entry_id == "3.50.0-0.3.pre")
    assert beta.title == "Flutter 3.50.0-0.3.pre (beta)"
    assert beta.url == "https://github.com/flutter/flutter/releases/tag/3.50.0-0.3.pre"
    assert "beta channel" in beta.raw_text


def test_version_missing_in_changelog_gets_generic_text():
    entries = make_parser().parse(read_fixture("flutter_releases_linux.json"), changelog="")
    assert entries[0].raw_text.startswith("Flutter 3.47.9 is available on the stable channel.")


def test_fetch_survives_changelog_failure():
    http = FakeHttp({RELEASES_URL: read_fixture("flutter_releases_linux.json"),
                     CHANGELOG_URL: FetchError("HTTP 503")})
    entries = make_parser(http).fetch()
    assert entries[0].entry_id == "3.47.9"


def test_major_release_links_to_release_notes_and_enriches_from_blog():
    http = FakeHttp({BLOG_URL: read_fixture("flutter_blog_3_47.html")})
    parser = make_parser(http)
    entries = parser.parse(releases_with_major(), read_fixture("flutter_CHANGELOG.md"))
    major = next(e for e in entries if e.entry_id == "3.47.0")
    assert major.url == "https://docs.flutter.dev/release/release-notes/release-notes-3.47.0"

    enriched = parser.enrich(major)
    assert http.calls == [BLOG_URL]
    assert enriched.raw_text.startswith(major.raw_text)
    assert "## Release blog post" in enriched.raw_text
    assert "Choose your own UI adventure" in enriched.raw_text  # заголовок раздела статьи
    assert "Share on LinkedIn" not in enriched.raw_text  # навигация отброшена


def test_enrich_skips_hotfixes_and_survives_blog_failure():
    http = FakeHttp({BLOG_URL: FetchError("HTTP 500")})
    parser = make_parser(http)
    entries = parser.parse(releases_with_major(), read_fixture("flutter_CHANGELOG.md"))
    hotfix = entries[0]
    assert parser.enrich(hotfix) is hotfix
    assert http.calls == []
    major = next(e for e in entries if e.entry_id == "3.47.0")
    assert parser.enrich(major) == major


def test_enrich_disabled_by_flag():
    http = FakeHttp()
    parser = make_parser(http, enrich_from_blog=False)
    entries = parser.parse(releases_with_major(), read_fixture("flutter_CHANGELOG.md"))
    major = next(e for e in entries if e.entry_id == "3.47.0")
    assert parser.enrich(major) is major
    assert http.calls == []
