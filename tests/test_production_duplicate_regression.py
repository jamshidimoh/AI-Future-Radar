import dedup
from main import _publication_text_within_limit, TELEGRAM_SAFE_TEXT_LIMIT


def test_protected_story_cannot_bypass_global_url_history(monkeypatch):
    link = "https://example.com/story-1"
    seen_hash = dedup._hash_link(link)
    monkeypatch.setattr(dedup, "load_seen", lambda: ({seen_hash}, []))
    monkeypatch.setattr(dedup, "_semantic_history_match", lambda item, signatures: 0.0)
    item = {
        "title": "Leader protected story",
        "link": link,
        "leader": "Leader",
        "protected_content": True,
        "_named_leader_interview": True,
    }
    assert dedup.filter_new_items([item], {seen_hash}) == []


def test_protected_publication_records_url_in_global_history(monkeypatch):
    item = {
        "title": "Protected story",
        "link": "https://example.com/protected",
        "protected_content": True,
        "leader": "Leader",
    }
    seen_hashes, seen_signatures, _ = dedup.mark_as_seen(item, set(), [], [])
    assert dedup._hash_link(item["link"]) in seen_hashes


def test_oversized_publication_is_rejected_before_delivery():
    assert _publication_text_within_limit("x" * TELEGRAM_SAFE_TEXT_LIMIT)
    assert not _publication_text_within_limit("x" * (TELEGRAM_SAFE_TEXT_LIMIT + 1))
