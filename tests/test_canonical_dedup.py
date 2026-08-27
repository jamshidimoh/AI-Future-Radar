import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import dedup
from publication_contract import TELEGRAM_SAFE_TEXT_LIMIT, unique_candidates, validate_publication_payload


def test_tracking_url_and_canonical_url_are_same_story():
    a = {"title": "OpenAI launches new model", "link": "https://example.com/story?utm_source=x&id=7"}
    b = {"title": "OpenAI launches new model", "link": "https://example.com/story?id=7&utm_campaign=y"}
    assert dedup._hash_link(a["link"]) == dedup._hash_link(b["link"])


def test_same_title_from_different_sources_is_blocked_cross_run():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "seen.json"
        with patch.object(dedup, "STATE_FILE", str(state)):
            seen_hashes = set()
            signatures = []
            item = {"title": "OpenAI launches new model", "link": "https://source-a.example/story"}
            seen_hashes, signatures, _ = dedup.mark_as_seen(item, seen_hashes, signatures, [])
            dedup.save_seen(seen_hashes, signatures, [])
            duplicate = {"title": "OpenAI launches new model", "link": "https://source-b.example/different-url"}
            assert dedup.filter_new_items([duplicate], seen_hashes) == []


def test_same_story_is_blocked_within_current_run():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "seen.json"
        with patch.object(dedup, "STATE_FILE", str(state)):
            items = [
                {"title": "OpenAI launches new model", "link": "https://a.example/story"},
                {"title": "OpenAI launches new model", "link": "https://b.example/story"},
            ]
            assert len(dedup.filter_new_items(items, set())) == 1


def test_protected_leader_story_is_still_blocked_on_next_run():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "seen.json"
        with patch.object(dedup, "STATE_FILE", str(state)):
            item = {
                "title": "Dario Amodei discusses AI safety",
                "link": "https://leader.example/interview?id=1",
                "protected_content": True,
                "_named_leader_interview": True,
                "leader": "Dario Amodei",
            }
            hashes, signatures, history = dedup.mark_as_seen(item, set(), [], [])
            dedup.save_seen(hashes, signatures, history)
            duplicate = dict(item, link="https://mirror.example/interview?id=99")
            assert dedup.filter_new_items([duplicate], hashes) == []


def test_rewritten_protected_leader_story_is_blocked_cross_run():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "seen.json"
        with patch.object(dedup, "STATE_FILE", str(state)):
            item = {
                "title": "Dario Amodei discusses AI safety and frontier risk",
                "description": "A detailed interview covers AI safety, frontier model risk and safeguards.",
                "link": "https://leader.example/interview?id=1",
                "protected_content": True,
                "_named_leader_interview": True,
                "leader": "Dario Amodei",
            }
            hashes, signatures, history = dedup.mark_as_seen(item, set(), [], [])
            dedup.save_seen(hashes, signatures, history)
            rewritten = {
                "title": "Frontier AI safety: Dario Amodei on model risk and safeguards",
                "description": "Dario Amodei explains safeguards for frontier AI models and the risks they create.",
                "link": "https://mirror.example/reframed-interview?id=99",
                "protected_content": True,
                "_named_leader_interview": True,
                "leader": "Dario Amodei",
            }
            assert dedup.filter_new_items([rewritten], hashes) == []


def test_leader_identity_is_persisted_in_source_history():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "seen.json"
        with patch.object(dedup, "STATE_FILE", str(state)):
            item = {
                "title": "Dario Amodei discusses AI safety",
                "link": "https://leader.example/interview?id=1",
                "protected_content": True,
                "_named_leader_interview": True,
                "leader": "Dario Amodei",
            }
            hashes, signatures, history = dedup.mark_as_seen(item, set(), [], [])
            dedup.save_seen(hashes, signatures, history)
            payload = json.loads(state.read_text(encoding="utf-8"))
            assert payload["source_history"][0]["leader"] == "Dario Amodei"


def test_state_has_no_duplicate_hashes_or_signatures():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "seen.json"
        with patch.object(dedup, "STATE_FILE", str(state)):
            hashes = set()
            signatures = []
            for i in range(3):
                item = {"title": f"Unique story {i}", "link": f"https://example.com/{i}"}
                hashes, signatures, _ = dedup.mark_as_seen(item, hashes, signatures, [])
            dedup.save_seen(hashes, signatures, [])
            payload = json.loads(state.read_text(encoding="utf-8"))
            assert len(payload["seen_hashes"]) == len(set(payload["seen_hashes"]))
            keys = [dedup._signature_key(x) for x in payload["seen_signatures"]]
            assert len(keys) == len(set(keys))


def test_same_url_with_changed_title_is_one_publication_candidate():
    items = [
        {"title": "Original title", "link": "https://example.com/story?utm_source=x"},
        {"title": "Updated title", "link": "https://example.com/story?utm_medium=y"},
    ]
    assert len(unique_candidates(items)) == 1


def test_protected_and_regular_candidates_share_url_identity():
    items = [
        {"title": "Leader version", "link": "https://example.com/story", "protected_content": True},
        {"title": "Regular version", "link": "https://example.com/story"},
    ]
    assert len(unique_candidates(items)) == 1


def test_oversized_payload_is_rejected_before_transport():
    ok, reason = validate_publication_payload("x" * (TELEGRAM_SAFE_TEXT_LIMIT + 1))
    assert ok is False
    assert reason.startswith("oversized_payload:")


def test_normal_payload_is_accepted():
    ok, reason = validate_publication_payload("خبر\nخلاصه\nمنبع")
    assert ok is True
    assert reason == "ok"
