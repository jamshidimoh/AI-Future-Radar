import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import dedup


def test_protected_leader_bypasses_historical_semantic_match(monkeypatch):
    candidate = {
        "title": "Dario Amodei on the next phase of AI safety",
        "link": "https://example.com/new",
        "protected_content": True,
        "leader_watch_protected": True,
        "content_type": "interview",
        "summary": "A substantive interview about frontier models, AI safety and deployment risks.",
    }
    monkeypatch.setattr(dedup, "load_seen", lambda: (set(), []))
    monkeypatch.setattr(dedup, "_semantic_history_match", lambda *args, **kwargs: 0.99)

    kept = dedup.filter_new_items([candidate], set())
    assert kept == [candidate]


def test_protected_leader_same_url_is_still_blocked(monkeypatch):
    candidate = {
        "title": "A new title",
        "link": "https://example.com/interview",
        "protected_content": True,
        "leader_watch_protected": True,
        "content_type": "interview",
    }
    url_hash = dedup._hash_link(candidate["link"])
    monkeypatch.setattr(dedup, "load_seen", lambda: (set(), [dedup.PROTECTED_MARKER + url_hash]))

    assert dedup.filter_new_items([candidate], set()) == []
