import json
import time

import src.publication_guard as publication_guard
import src.publication_index as publication_index


def test_exact_identities_are_retained_beyond_semantic_window():
    now = 2_000_000_000.0
    old = now - 45 * 86400
    index = publication_index.PublicationIndex(
        [
            {
                "title": "Historic OpenAI research announcement",
                "link": "https://example.com/historic-story?utm_source=old",
                "posted_at": old,
            }
        ],
        now=now,
    )

    assert index.has_url("https://example.com/historic-story?utm_medium=new")
    assert index.has_title("Historic OpenAI research announcement")
    assert index.semantic_records == []


def test_semantic_history_is_limited_to_30_days_and_200_records():
    now = 2_000_000_000.0
    recent = [
        {
            "title": f"OpenAI launches research system {number}",
            "summary": f"OpenAI announces a new research system, version {number}.",
            "link": f"https://example.com/recent/{number}",
            "posted_at": now - number * 3600,
        }
        for number in range(210)
    ]
    old = {
        "title": "OpenAI announces a very old research system",
        "summary": "A separate historical announcement.",
        "link": "https://example.com/old",
        "posted_at": now - 45 * 86400,
    }
    index = publication_index.PublicationIndex([old, *recent], now=now)

    assert len(index.semantic_records) == 200
    assert all(item["link"] != old["link"] for item in index.semantic_records)


def test_detailed_semantic_candidate_list_never_exceeds_ten():
    now = 2_000_000_000.0
    records = [
        {
            "title": f"OpenAI announces a new foundation model development {number}",
            "summary": f"OpenAI model announcement with research details {number}.",
            "link": f"https://example.com/story/{number}",
            "posted_at": now - number * 60,
        }
        for number in range(200)
    ]
    index = publication_index.PublicationIndex(records, now=now)
    selected = index.semantic_candidates(
        {
            "title": "OpenAI announces a new foundation model development",
            "summary": "OpenAI shares research details about a new model.",
        }
    )

    assert len(selected) <= 10
    assert index.metrics()["semantic_comparisons"] == 0


def test_feedback_file_is_loaded_once_while_unchanged(tmp_path, monkeypatch):
    publication_index.clear_publication_caches()
    path = tmp_path / "telegram_feedback.json"
    path.write_text(
        json.dumps({"messages": {"1": {"title": "Cached story", "link": "https://example.com/1"}}}),
        encoding="utf-8",
    )
    original = publication_index.load_json_state
    calls = []

    def counted_load(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(publication_index, "load_json_state", counted_load)

    first = publication_index.load_feedback_records(path)
    second = publication_index.load_feedback_records(path)

    assert first is second
    assert len(calls) == 1


def test_old_semantic_rewrite_expires_but_exact_url_stays_blocked(tmp_path, monkeypatch):
    path = tmp_path / "telegram_feedback.json"
    posted_at = int(time.time()) - 45 * 86400
    path.write_text(
        json.dumps(
            {
                "messages": {
                    "1": {
                        "title": "OpenAI launches a new reasoning model",
                        "summary": "OpenAI launches a new reasoning model for enterprise users.",
                        "link": "https://example.com/old-openai",
                        "posted_at": posted_at,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(publication_guard, "LEDGER_PATH", path)
    publication_index.clear_publication_caches()

    rewritten = (
        "<b>📡 OpenAI introduces its latest reasoning model for enterprise users</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nOpenAI introduces a new reasoning model for enterprise use.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(
        rewritten, "https://another.example/openai-rewrite"
    )
    assert allowed, reason

    exact_url_allowed, exact_url_reason = publication_guard.check_before_publish(
        rewritten, "https://example.com/old-openai?utm_source=telegram"
    )
    assert not exact_url_allowed
    assert exact_url_reason == "canonical_url_already_published"


def test_material_update_is_not_suppressed_as_a_duplicate(tmp_path, monkeypatch):
    path = tmp_path / "telegram_feedback.json"
    path.write_text(
        json.dumps(
            {
                "messages": {
                    "1": {
                        "title": "OpenAI announces GPT-6 model with 1 trillion parameters",
                        "summary": "OpenAI says GPT-6 will launch in 2027 with 1 trillion parameters.",
                        "link": "https://example.com/gpt6-original",
                        "posted_at": int(time.time()),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(publication_guard, "LEDGER_PATH", path)
    publication_index.clear_publication_caches()

    updated = (
        "<b>📡 OpenAI announces GPT-6 model with 2 trillion parameters</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nOpenAI says GPT-6 will launch in 2027 with 2 trillion parameters.</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(
        updated, "https://example.com/gpt6-update"
    )

    assert allowed, reason



def test_confirmed_delivery_refreshes_an_existing_index_after_ledger_write(tmp_path):
    path = tmp_path / "telegram_feedback.json"
    first = {
        "title": "First published research story",
        "summary": "A published research story.",
        "link": "https://example.com/first",
        "posted_at": int(time.time()),
    }
    second = {
        "title": "Second published research story",
        "summary": "Another published research story.",
        "link": "https://example.com/second",
        "posted_at": int(time.time()),
    }
    path.write_text(
        json.dumps({"messages": {"1": first}}, ensure_ascii=False),
        encoding="utf-8",
    )
    publication_index.clear_publication_caches()
    records = publication_index.load_feedback_records(path)
    index = publication_index.cached_publication_index(
        records,
        cache_key=(str(path.resolve()),),
    )
    assert not index.has_url(second["link"])

    # Simulate the Telegram ledger callback persisting the confirmed message
    # before the in-memory publication cache receives its update.
    path.write_text(
        json.dumps({"messages": {"1": first, "2": second}}, ensure_ascii=False),
        encoding="utf-8",
    )
    publication_index.remember_feedback_record(path, second)

    assert index.has_url(second["link"])
    assert len(index.records) == 2
