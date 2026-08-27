from publication_contract import TELEGRAM_SAFE_TEXT_LIMIT, unique_candidates, validate_publication_payload


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
