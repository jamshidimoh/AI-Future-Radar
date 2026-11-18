import json

import pytest

from scripts.omniroute_provider_output import parse_provider_list


def test_parses_json_provider_object():
    rows = [{"id": "provider-1", "provider": "openrouter"}]
    assert parse_provider_list(json.dumps({"providers": rows})) == rows


def test_parses_top_level_json_array():
    rows = [{"id": "provider-1", "provider": "openrouter"}]
    assert parse_provider_list(json.dumps(rows)) == rows


def test_parses_json_with_ansi_and_cli_preamble():
    rows = [{"id": "provider-1", "provider": "openrouter"}]
    raw = "\x1b[32mConnected providers:\x1b[0m\n" + json.dumps({"providers": rows})
    assert parse_provider_list(raw) == rows


@pytest.mark.parametrize("raw", ["", "not-json", "{broken", "Connected: yes"])
def test_rejects_empty_or_malformed_output(raw):
    with pytest.raises(ValueError):
        parse_provider_list(raw)


def test_rejects_unexpected_json_shape():
    with pytest.raises(ValueError):
        parse_provider_list('{"items": []}')


def test_rejects_non_object_provider_entries():
    with pytest.raises(ValueError):
        parse_provider_list('{"providers": ["openrouter"]}')
