import json

import pytest

from bot.state import State, StateError


def test_new_file_and_initialize(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    assert not state.has_source("dart")
    state.initialize("dart", ["3.13.5", "3.13.6", "3.13.7"])
    assert state.has_source("dart")
    assert state.seen_ids("dart") == {"3.13.5", "3.13.6", "3.13.7"}
    assert state.save() is True
    data = json.loads(path.read_text())
    assert data["sources"]["dart"]["seen"] == ["3.13.5", "3.13.6", "3.13.7"]


def test_save_only_when_changed(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    state.initialize("a", ["1"])
    assert state.save() is True
    mtime = path.stat().st_mtime_ns
    assert state.save() is False
    state.mark_seen("a", "1")  # повтор того же ID не меняет файл
    assert state.save() is False
    assert path.stat().st_mtime_ns == mtime
    state.mark_seen("a", "2")
    assert state.save() is True


def test_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    state.initialize("a", ["1", "2"])
    state.save()
    again = State(path)
    assert again.has_source("a")
    assert again.seen_ids("a") == {"1", "2"}
    assert again.save() is False


def test_keep_limit_drops_oldest(tmp_path):
    state = State(tmp_path / "state.json", keep=3)
    state.initialize("a", ["1", "2", "3"])
    state.mark_seen("a", "4")
    assert state.seen_ids("a") == {"2", "3", "4"}


def test_empty_seen_list_still_counts_as_initialized(tmp_path):
    state = State(tmp_path / "state.json")
    state.initialize("a", [])
    assert state.has_source("a")


def test_corrupted_file_is_an_error(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")
    with pytest.raises(StateError):
        State(path)
