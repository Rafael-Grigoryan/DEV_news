import os
from pathlib import Path

import pytest

from bot.config import ConfigError, load_config, load_dotenv
from bot.parsers import PARSERS

ROOT = Path(__file__).parent.parent


def test_project_sources_yaml_is_valid():
    config = load_config(ROOT / "sources.yaml")
    ids = [s.id for s in config.sources]
    assert ids == ["claude_code", "claude_api", "claude_apps", "flutter", "dart"]
    assert all(s.type in PARSERS for s in config.sources)
    flutter = next(s for s in config.sources if s.id == "flutter")
    assert flutter.include_prereleases is False
    assert flutter.opt("enrich_from_blog") is True
    assert flutter.opt("changelog_url").endswith("/CHANGELOG.md")
    assert all(s.max_entries < config.settings.state_keep for s in config.sources)


def write(tmp_path, text):
    path = tmp_path / "sources.yaml"
    path.write_text(text, encoding="utf-8")
    return path


BASE = "sources:\n  - {id: a, name: A, type: rss, url: 'https://x'}\n"


def test_settings_defaults_and_per_source_override(tmp_path):
    config = load_config(write(tmp_path, "settings: {max_posts_per_run: 2}\n" + BASE +
                               "  - {id: b, name: B, type: rss, url: 'https://y', max_posts_per_run: 7}\n"))
    assert [s.max_posts_per_run for s in config.sources] == [2, 7]
    assert config.sources[0].link_text == "Полный changelog"


@pytest.mark.parametrize("text, message", [
    (BASE + "  - {id: a, name: A2, type: rss, url: 'https://y'}\n", "повторяющийся"),
    ("sources:\n  - {id: a, name: A, type: nope, url: 'https://x'}\n", "неизвестный type"),
    ("sources:\n  - {id: a, name: A, type: rss}\n", "url"),
    ("sources:\n  - {id: Bad-Id, name: A, type: rss, url: 'https://x'}\n", "id источника"),
    ("settings: {typo: 1}\n" + BASE, "неизвестные ключи"),
    ("settings: {state_keep: 10}\n" + BASE, "state_keep"),
    ("sources: []\n", "нет ни одного"),
])
def test_invalid_configs(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, text))


def test_load_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEP_ME", "from-env")
    for key in ("PLAIN", "QUOTED", "EXPORTED"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text('# comment\nPLAIN=value\nQUOTED="with spaces"\nexport EXPORTED=1\nKEEP_ME=from-file\n\nbroken\n')
    load_dotenv(env)
    assert os.environ["PLAIN"] == "value"
    assert os.environ["QUOTED"] == "with spaces"
    assert os.environ["EXPORTED"] == "1"
    assert os.environ["KEEP_ME"] == "from-env"
    for key in ("PLAIN", "QUOTED", "EXPORTED"):
        monkeypatch.delenv(key)
