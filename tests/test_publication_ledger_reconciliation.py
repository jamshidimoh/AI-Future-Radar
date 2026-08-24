import json


def test_telegram_ledger_reconciles_missing_seen_state(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, "src")
    import dedup

    state = tmp_path / "seen.json"
    feedback = tmp_path / "telegram_feedback.json"
    state.write_text(json.dumps({"seen_hashes": [], "seen_signatures": []}), encoding="utf-8")
    feedback.write_text(json.dumps({
        "messages": {
            "-100:123": {
                "message_id": 123,
                "content_type": "news",
                "title": "چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی",
                "link": "https://example.com/story-123",
            }
        }
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(dedup, "STATE_FILE", str(state))
    monkeypatch.setattr(dedup, "FEEDBACK_FILE", str(feedback))

    seen_hashes, seen_signatures = dedup.load_seen()
    candidate = {
        "title": "چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی",
        "link": "https://example.com/story-123",
        "content_type": "news",
    }
    assert dedup._story_id(candidate) in dedup._stored_story_ids(seen_signatures)
    assert dedup.filter_new_items([candidate], seen_hashes) == []


def test_ledger_reconciles_rewritten_title_semantically(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, "src")
    import dedup

    state = tmp_path / "seen.json"
    feedback = tmp_path / "telegram_feedback.json"
    state.write_text(json.dumps({"seen_hashes": [], "seen_signatures": []}), encoding="utf-8")
    feedback.write_text(json.dumps({
        "messages": {
            "-100:124": {
                "message_id": 124,
                "content_type": "news",
                "title": "AI در تعامل با دنیای فیزیکی با چالش‌های جدی روبه‌روست",
                "summary": "سامانه‌های هوش مصنوعی هنگام تعامل با محیط فیزیکی با محدودیت‌های مهمی مواجه‌اند.",
                "link": "https://example.com/story-124",
            }
        }
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(dedup, "STATE_FILE", str(state))
    monkeypatch.setattr(dedup, "FEEDBACK_FILE", str(feedback))

    seen_hashes, _ = dedup.load_seen()
    candidate = {
        "title": "چالش‌های هوش مصنوعی هنگام تعامل با جهان فیزیکی",
        "summary": "هوش مصنوعی برای کار در جهان فیزیکی همچنان با چالش‌های مهمی روبه‌رو است.",
        "link": "https://example.com/new-source-url",
        "content_type": "news",
    }
    assert dedup.filter_new_items([candidate], seen_hashes) == []
