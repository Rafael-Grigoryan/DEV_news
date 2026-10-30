import json

from bot.parsers.github_releases import GithubReleasesParser
from bot.parsers.rss import RssParser
from tests.conftest import make_source, read_fixture

API_URL = "https://api.github.com/repos/flutter/flutter/releases?per_page=30"


def github_parser(**kwargs):
    return GithubReleasesParser(make_source(name="Flutter", type="github_releases", url=API_URL, **kwargs), None)


def test_github_prerelease_detected_by_tag_even_if_flag_is_false():
    # У flutter/flutter все 7 релизов — беты с prerelease=false; по тегу видно, что это .pre
    assert github_parser().parse(read_fixture("github_releases_flutter.json")) == []


def test_github_include_prereleases():
    entries = github_parser(include_prereleases=True).parse(read_fixture("github_releases_flutter.json"))
    assert [e.entry_id for e in entries][:2] == ["3.19.0-0.1.pre", "3.18.0-0.1.pre"]
    assert entries[0].title == "Flutter 3.19.0-0.1.pre"
    assert entries[0].url == "https://github.com/flutter/flutter/releases/tag/3.19.0-0.1.pre"
    assert entries[0].raw_text


def test_github_stable_and_draft():
    releases = json.loads(read_fixture("github_releases_flutter.json"))
    releases.insert(0, {**releases[0], "tag_name": "v3.20.0", "name": "Flutter 3.20", "prerelease": False,
                        "published_at": "2024-02-15T00:00:00Z"})
    releases.insert(0, {**releases[0], "tag_name": "v3.21.0", "draft": True})
    entries = github_parser(title_from="tag").parse(json.dumps(releases))
    assert [e.entry_id for e in entries] == ["v3.20.0"]
    assert entries[0].title == "Flutter 3.20.0"
    named = github_parser(title_from="name").parse(json.dumps(releases))
    assert named[0].title == "Flutter Flutter 3.20"


def rss_parser(**kwargs):
    return RssParser(make_source(name="Feed", type="rss", url="https://example.com/feed", **kwargs), None)


def test_atom_feed():
    entries = rss_parser().parse(read_fixture("flutter_blog_feed.atom.xml"))
    assert len(entries) == 5
    first = entries[0]
    assert first.title == "AI makes it easy to migrate. Flutter makes it easy to scale."
    assert first.entry_id == first.url == (
        "https://flutter.dev/blog/ai-makes-it-easy-to-migrate-flutter-makes-it-easy-to-scale"
    )
    assert first.published_at.isoformat().startswith("2026-10-20")
    assert first.raw_text.startswith("Why verification speed")
    assert entries == sorted(entries, key=lambda e: e.published_at, reverse=True)


def test_rss_feed_with_title_filter_and_prefix():
    entries = rss_parser().parse(read_fixture("python_insider.rss.xml"))
    assert len(entries) == 3
    assert entries[0].title.startswith("Python 3.15.2")
    assert entries[0].entry_id == "https://blog.python.org/2026/10/python-3152-31410-31318-31216-31118/"
    assert entries[0].published_at is not None
    assert "<" not in entries[0].raw_text

    # только стабильные релизы: «... are out», без «alpha»
    filtered = rss_parser(title_regex=r"are out$", title_prefix=True).parse(read_fixture("python_insider.rss.xml"))
    assert [e.title for e in filtered] == [
        "Feed: Python 3.15.2, 3.14.10, 3.13.18, 3.12.16 and 3.11.18 are out",
        "Feed: Python 3.15.1, 3.14.9 and 3.13.17 are out",
    ]
