import json

import src.dedup as dedup
import src.publication_guard as publication_guard
from src.event_identity import compare_events
from src.publication_index import (
    MAX_SEMANTIC_COMPARISONS,
    SEMANTIC_HISTORY_LIMIT,
    PublicationIndex,
    clear_publication_index_cache,
)


def test_all_time_exact_identities_survive_semantic_lookback():
    now = 1_900_000_000
    old = {
        "title": "OpenAI launches a major AI research model",
        "link": "https://example.com/old-story?utm_source=archive",
        "posted_at": now - 60 * 86400,
    }
    index = PublicationIndex([old], now=now)

    assert index.semantic_window_count == 0
    assert index.contains_url("https://example.com/old-story")
    assert index.contains_title("OpenAI launches a major AI research model")


def test_semantic_window_is_limited_to_recent_200_records():
    now = 1_900_000_000
    recent = [
        {
            "title": f"OpenAI launches GPT-6 feature {i}",
            "summary": "OpenAI launches a GPT-6 feature for AI agents.",
            "link": f"https://example.com/recent/{i}",
            "posted_at": now - i * 60,
        }
        for i in range(SEMANTIC_HISTORY_LIMIT + 35)
    ]
    old = {
        "title": "OpenAI launches a separate historical product",
        "link": "https://example.com/old",
        "posted_at": now - 60 * 86400,
    }
    index = PublicationIndex([old, *recent], now=now)

    assert index.record_count == len(recent) + 1
    assert index.semantic_window_count == SEMANTIC_HISTORY_LIMIT
    assert index.contains_url(old["link"])
    assert old not in index.semantic_records


def test_semantic_candidate_comparisons_are_hard_capped_at_ten():
    now = 1_900_000_000
    records = [
        {
            "title": f"OpenAI launches GPT-6 Astra for enterprise work {i}",
            "summary": "OpenAI launches GPT-6 Astra for enterprise AI workflows.",
            "link": f"https://example.com/story/{i}",
            "posted_at": now - i * 60,
        }
        for i in range(25)
    ]
    index = PublicationIndex(records, now=now)
    candidate = {
        "title": "OpenAI launches GPT-6 Astra for enterprise work",
        "summary": "OpenAI launches GPT-6 Astra for enterprise AI workflows.",
        "link": "https://example.com/new-story",
    }

    matches = index.semantic_candidates(candidate, limit=100)

    assert len(matches) == MAX_SEMANTIC_COMPARISONS


def test_material_update_is_not_blocked_as_same_story(tmp_path, monkeypatch):
    ledger_path = tmp_path / "telegram_feedback.json"
    ledger_path.write_text(json.dumps({"messages": {}}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(publication_guard, "LEDGER_PATH", ledger_path)
    clear_publication_index_cache(ledger_path)

    old = {
        "title": "OpenAI launches GPT-6 with a 1 million token context window",
        "summary": "OpenAI launches GPT-6 with a 1 million token context window for enterprise AI assistants.",
        "link": "https://example.com/gpt6-old",
    }
    updated_title = "OpenAI launches GPT-6 with a 2 million token context window"
    updated_summary = (
        "OpenAI launches GPT-6 with a 2 million token context window for enterprise AI assistants "
        "and adds expanded multimodal input support."
    )

    event_kind, _, _ = compare_events(
        {"title": updated_title, "summary": updated_summary},
        old,
    )
    assert event_kind == "UPDATE"
    assert publication_guard._semantic_conflict(updated_title, updated_summary, old) == 0.0

    rendered = (
        f"<b>📡 {updated_title}</b>\n"
        f"<blockquote>📌 <b>خلاصه</b>\n{updated_summary}</blockquote>"
    )
    allowed, reason = publication_guard.check_before_publish(
        rendered,
        "https://example.com/gpt6-updated",
        records=[old],
    )

    assert allowed, reason


def test_model_version_change_is_not_misclassified_as_material_update():
    previous = {
        "title": "OpenAI launches GPT-5 with advanced reasoning for enterprise work",
        "summary": "OpenAI launches GPT-5 with advanced reasoning capabilities for enterprise AI workflows.",
    }
    candidate = {
        "title": "OpenAI launches GPT-6 with advanced reasoning for enterprise work",
        "summary": "OpenAI launches GPT-6 with advanced reasoning capabilities for enterprise AI workflows.",
    }

    event_kind, _, _ = compare_events(candidate, previous)

    assert event_kind == "DUPLICATE"




def test_untimestamped_records_are_not_mixed_into_dated_history():
    now = 1_900_000_000
    recent = {
        "title": "OpenAI launches GPT-6 enterprise agents",
        "link": "https://example.com/recent",
        "posted_at": now - 3600,
    }
    unknown_age = {
        "title": "OpenAI launches an old unrelated platform",
        "link": "https://example.com/unknown-age",
    }
    index = PublicationIndex([unknown_age, recent], now=now)

    assert index.semantic_records == [recent]



def test_education_posts_do_not_enter_news_duplicate_index():
    education = {
        "content_type": "education",
        "title": "AI and Machine Learning foundations",
        "link": "https://example.com/lesson-1",
    }
    news = {
        "content_type": "news",
        "title": "AI and Machine Learning foundations",
        "link": "https://example.com/news-story",
    }
    index = PublicationIndex([education, news])

    assert index.record_count == 2
    assert index.semantic_records == [news]
    assert not index.contains_url(education["link"])
    assert index.contains_url(news["link"])



def test_load_seen_reconciles_all_time_url_hashes_but_not_old_semantic_history(tmp_path, monkeypatch):
    now = 1_900_000_000
    ledger_path = tmp_path / "telegram_feedback.json"
    state_path = tmp_path / "seen.json"
    old = {
        "title": "OpenAI launches an old AI research model",
        "link": "https://example.com/old-ledger-story",
        "posted_at": now - 60 * 86400,
        "content_type": "news",
    }
    ledger_path.write_text(
        json.dumps({"messages": {"1": old}}, ensure_ascii=False),
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps({"seen_hashes": [], "seen_signatures": [], "source_history": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(dedup, "FEEDBACK_FILE", str(ledger_path))
    monkeypatch.setattr(dedup, "STATE_FILE", str(state_path))
    clear_publication_index_cache(ledger_path)

    hashes, signatures = dedup.load_seen()

    assert dedup._hash_link(old["link"]) in hashes
    assert not any(
        isinstance(value, str) and value.startswith(dedup.SEMANTIC_MARKER)
        for value in signatures
    )

def test_legacy_ledger_without_timestamps_keeps_small_semantic_fallback():
    old_records = [
        {
            "title": "Andrew Ng announces a new AI education course",
            "summary": "Andrew Ng announces a practical AI education course for developers.",
            "link": "https://example.com/course",
        }
    ]
    index = PublicationIndex(old_records, now=1_900_000_000)

    assert index.semantic_window_count == 1
    assert index.semantic_candidates(
        {
            "title": "Andrew Ng announces a new AI education course",
            "summary": "Andrew Ng announces a practical AI education course for developers.",
        }
    ) == old_records
