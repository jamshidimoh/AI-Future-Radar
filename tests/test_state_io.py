import json

import pytest

from src.dedup import _load_state
from src.state_io import StateCorruptionError, load_json_state


def test_missing_file_returns_default(tmp_path):
    default = {"missing": True}
    assert load_json_state(tmp_path / "state.json", default, label="test state") is default


def test_valid_json_returns_parsed_value(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"value": 3}), encoding="utf-8")
    assert load_json_state(path, {}, label="test state") == {"value": 3}


def test_corrupt_json_raises_state_corruption_error(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(StateCorruptionError, match="test state"):
        load_json_state(path, {}, label="test state")


def test_directory_in_place_of_file_raises_state_corruption_error(tmp_path):
    path = tmp_path / "state.json"
    path.mkdir()
    with pytest.raises(StateCorruptionError, match="test state"):
        load_json_state(path, {}, label="test state")


def test_dedup_load_state_raises_on_corruption(monkeypatch, tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{", encoding="utf-8")
    monkeypatch.setattr("src.dedup.STATE_FILE", str(path))
    with pytest.raises(StateCorruptionError, match="seen state"):
        _load_state()
