# ruff: noqa: I001
from pathlib import Path

from src.people_watch import bootstrap_candidates, build_bootstrap_state, deduplicate_people_signals, filter_people_person_cooldown, load_people_watchlist, post_bootstrap_candidates, reconcile_people_bootstrap_state, relevant_people_item


ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "config" / "leader_watchlist.yaml"


def _item(person, published, suffix, *, title_suffix="") -> dict:
    return {
        "watch_person": person,
        "leader": person,
        "person_name": person,
        "title": f"{person} discusses AI {title_suffix}".strip(),
        "summary": f"{person} gives a substantive technology and AI perspective {title_suffix}".strip(),
        "content_type": "interview",
        "published": published,
        "link": f"https://example.com/{suffix}",
    }


def test_watchlist_has_exactly_30_people():
    people = load_people_watchlist(WATCHLIST)
    assert len(people) == 30
    assert len(set(people)) == 30
    assert "Andrew Ng" in people
    assert "Yuval Noah Harari" in people
    assert "Eric Schmidt" in people
    assert "Elon Musk" in people
    assert "Jensen Huang" in people
    assert "Sam Altman" in people


def test_bootstrap_prefers_authoritative_source_over_newer_weak_source():
    people = ["Andrew Ng"]
    weak = _item("Andrew Ng", "2026-10-03 10:00", "weak")
    weak["source_tier"] = 3
    strong = _item("Andrew Ng", "2026-09-30 10:00", "strong")
    strong["source_tier"] = 1
    selected = bootstrap_candidates([weak, strong], people, seen_hashes=set())
    assert len(selected) == 1
    assert selected[0]["link"] == strong["link"]
    assert selected[0]["people_bootstrap_validated"] is True


def test_bootstrap_picks_one_latest_content_per_person_even_when_old():
    people = load_people_watchlist(WATCHLIST)
    items = [
        _item(person, "2025-01-01 10:00", f"old-{index}", title_suffix="long-form interview")
        for index, person in enumerate(people)
    ]
    selected = bootstrap_candidates(items, people, seen_hashes=set())
    assert len(selected) == 30
    assert [item["person_name"] for item in selected] == people
    assert all(item["people_bootstrap"] for item in selected)




def test_bootstrap_replaces_stale_undelivered_baseline_with_newer_signal():
    people = ["Sam Altman"]
    old = _item("Sam Altman", "2026-09-22 10:00", "old")
    newer = _item("Sam Altman", "2026-09-25 08:00", "new")
    selected = bootstrap_candidates(
        [old, newer],
        people,
        previous_state={
            "baseline": {
                "Sam Altman": {
                    "title": old["title"],
                    "link": old["link"],
                    "published": old["published"],
                }
            },
            "delivered_people": [],
        },
        seen_hashes=set(),
    )
    assert len(selected) == 1
    assert selected[0]["link"] == newer["link"]
    assert selected[0]["published"] == newer["published"]


def test_post_bootstrap_returns_all_new_independent_signals_without_person_quota():
    people = ["Sam Altman"]
    items = [
        _item("Sam Altman", f"2026-09-22 {10 + index:02d}:00", f"sig-{index}", title_suffix=str(index))
        for index in range(5)
    ]
    selected = post_bootstrap_candidates(
        items,
        people,
        bootstrap_at="2026-09-22T09:00:00+00:00",
        seen_hashes=set(),
    )
    assert len(selected) == 5
    assert all(item["people_lane"] for item in selected)
    assert {item["person_name"] for item in selected} == {"Sam Altman"}



def test_relevant_people_item_does_not_treat_ai_substring_as_mission_evidence():
    item = {
        "watch_person": "Sam Altman",
        "leader": "Sam Altman",
        "title": "Sam Altman appears at a daily business briefing",
        "summary": "The briefing covers company results and quarterly operations.",
        "content_type": "news",
        "published": "2026-09-22 10:00",
        "link": "https://example.com/daily-briefing",
    }
    assert relevant_people_item(item, "Sam Altman") is False

def test_relevant_people_item_does_not_trust_mission_terms_in_discovery_query():
    item = {
        "watch_person": "Sam Altman",
        "leader": "Sam Altman",
        "title": "Sam Altman appears at a daily business briefing",
        "summary": "The briefing covers company results and quarterly operations.",
        "content_type": "news",
        "discovery_query": '"Sam Altman" (interview OR podcast OR AI OR AGI OR future)',
        "published": "2026-09-22 10:00",
        "link": "https://example.com/daily-briefing-query-false-positive",
    }
    assert relevant_people_item(item, "Sam Altman") is False


def test_relevant_people_item_accepts_interview_without_explicit_mission_term():
    item = {
        "watch_person": "Sam Altman",
        "leader": "Sam Altman",
        "title": "Sam Altman in conversation on the future",
        "summary": "A long-form interview with Sam Altman.",
        "content_type": "interview",
        "published": "2026-09-22 10:00",
        "link": "https://example.com/interview",
    }
    assert relevant_people_item(item, "Sam Altman") is True


def test_people_dedup_removes_exact_duplicate_identity_but_keeps_independent_signals():
    items = [
        {
            **_item("Sam Altman", "2026-09-22 10:00", "same", title_suffix="A"),
            "title": "Sam Altman announces agent research direction",
            "summary": "Sam Altman outlines a new agent research direction in a dedicated interview.",
        },
        {
            **_item("Sam Altman", "2026-09-22 10:00", "same", title_suffix="A"),
            "title": "Sam Altman announces agent research direction",
            "summary": "Sam Altman outlines a new agent research direction in a dedicated interview.",
        },
        {
            **_item("Sam Altman", "2026-09-22 11:00", "independent", title_suffix="B"),
            "title": "Sam Altman discusses AI education strategy",
            "summary": "Sam Altman discusses a separate strategy for AI education and learning.",
        },
    ]
    selected = deduplicate_people_signals(items, seen_signatures=[])
    assert len(selected) == 2
    assert {item["link"] for item in selected} == {
        "https://example.com/same",
        "https://example.com/independent",
    }


def test_bootstrap_keeps_same_url_for_different_people():
    people = ["Sam Altman", "Dario Amodei"]
    items = [
        {**_item("Sam Altman", "2025-01-01 10:00", "shared"), "title": "Shared event", "summary": "Sam Altman discusses AI."},
        {**_item("Dario Amodei", "2025-01-01 10:05", "shared"), "title": "Shared event", "summary": "Dario Amodei discusses AI."},
    ]
    selected = bootstrap_candidates(items, people, seen_hashes=set())
    assert len(selected) == 2
    assert {item["person_name"] for item in selected} == set(people)


def test_post_bootstrap_uses_historical_people_signatures():
    people = ["Sam Altman"]
    historical = _item("Sam Altman", "2026-09-22 10:00", "old-url")
    current_same_event = {
        **_item("Sam Altman", "2026-09-22 11:00", "new-url"),
        "title": historical["title"],
        "summary": historical["summary"],
        "description": historical.get("description", ""),
    }
    from src.semantic_dedup import get_story_signature
    selected = post_bootstrap_candidates(
        [current_same_event],
        people,
        bootstrap_at="2026-09-22T09:00:00+00:00",
        seen_hashes=set(),
    )
    selected = deduplicate_people_signals(
        selected,
        seen_signatures=[get_story_signature(historical)],
    )
    assert selected == []


def test_bootstrap_state_records_same_checkpoint_and_delivery_progress():
    candidate = _item("Sam Altman", "2026-01-01 10:00", "baseline")
    state = build_bootstrap_state(
        bootstrap_at="2026-09-22T09:00:00+00:00",
        candidates=[candidate],
        delivered_people=["Sam Altman"],
        status="complete",
    )
    assert state["bootstrap_at"] == "2026-09-22T09:00:00+00:00"
    assert state["status"] == "complete"
    assert state["people_count"] == 1
    assert state["delivered_count"] == 1
    assert state["baseline"]["Sam Altman"]["link"] == "https://example.com/baseline"



def test_relevant_people_item_rejects_query_and_category_only_false_positive():
    item = {
        "watch_person": "Kate Crawford",
        "leader": "Kate Crawford",
        "title": "Adam Sandler officiates a wedding",
        "summary": "The event included celebrity guests and commentary.",
        "category": "ai",
        "topic_family": "future",
        "content_type": "news",
        "discovery_query": '"Kate Crawford" (AI OR AGI OR future)',
        "published": "2026-09-22 10:00",
        "link": "https://example.com/false-positive",
    }
    assert relevant_people_item(item, "Kate Crawford") is False


def test_relevant_people_item_requires_person_evidence_not_watch_metadata():
    item = {
        "watch_person": "George Church",
        "leader": "George Church",
        "title": "A local church opens a new community center",
        "summary": "The neighborhood project is unrelated to biotechnology.",
        "category": "ai",
        "content_type": "news",
        "published": "2026-09-22 10:00",
        "link": "https://example.com/name-collision",
    }
    assert relevant_people_item(item, "George Church") is False



def test_people_relevance_ignores_category_topic_and_generic_leader_query_metadata():
    item = {
        "watch_person": "Kate Crawford",
        "leader": "Kate Crawford",
        "title": "Adam Sandler officiates a wedding",
        "summary": "Celebrity news and commentary.",
        "category": "ai",
        "topic_family": "future",
        "content_type": "leader_signal",
        "discovery_query": '"Kate Crawford" (statement OR AI OR future)',
        "published": "2026-09-22 10:00",
        "link": "https://example.com/kate-false-positive-2",
    }
    assert relevant_people_item(item, "Kate Crawford") is False


def test_people_person_cooldown_rotates_recently_published_people():
    items = [
        _item("Sam Altman", "2026-09-27 09:00", "sam-new"),
        _item("Dario Amodei", "2026-09-27 08:00", "dario-new"),
    ]
    history = [
        {"leader": "Sam Altman", "ts": 1, "content_type": "interview"},
        {"leader": "Jensen Huang", "ts": 2, "content_type": "news"},
    ]
    kept, blocked = filter_people_person_cooldown(items, history, window=8)
    assert blocked == 1
    assert len(kept) == 1
    assert kept[0]["person_name"] == "Dario Amodei"



def test_people_person_cooldown_does_not_block_protected_leader():
    item = _item("Sam Altman", "2026-09-27 09:00", "protected")
    item["protected_content"] = True
    kept, blocked = filter_people_person_cooldown(
        [item],
        [{"leader": "Sam Altman", "content_type": "interview", "ts": 1}],
        window=8,
    )
    assert kept == [item]
    assert blocked == 0


def test_people_person_cooldown_fails_open_when_all_candidates_are_same_recent_person():
    items = [
        _item("Sam Altman", "2026-09-27 09:00", "one"),
        _item("Sam Altman", "2026-09-27 08:00", "two"),
    ]
    kept, blocked = filter_people_person_cooldown(
        items,
        [{"leader": "Sam Altman", "content_type": "interview", "ts": 1}],
        window=8,
    )
    assert len(kept) == 1
    assert blocked == 1


def test_bootstrap_reconciles_successful_people_publication_from_telegram_ledger(tmp_path):
    feedback = tmp_path / "telegram_feedback.json"
    feedback.write_text(
        """{
            "messages": {
                "channel:1942": {
                    "people_lane": true,
                    "person_name": "Nick Bostrom",
                    "leader": "Nick Bostrom",
                    "title": "نیک بستروم: توقف توسعه هوش مصنوعی با هزینه همراه است",
                    "link": "https://example.com/bostrom"
                }
            }
        }""",
        encoding="utf-8",
    )
    state = {
        "status": "in_progress",
        "baseline": {"Nick Bostrom": {"title": "old", "link": "old", "published": "2026-09-21"}},
        "delivered_people": [],
    }
    reconciled = reconcile_people_bootstrap_state(
        state,
        people=["Nick Bostrom"],
        feedback_path=feedback,
    )
    assert "Nick Bostrom" in reconciled["delivered_people"]

    candidate = _item("Nick Bostrom", "2026-09-27 10:00", "new-bostrom")
    selected = bootstrap_candidates(
        [candidate],
        ["Nick Bostrom"],
        previous_state=reconciled,
        seen_hashes=set(),
    )
    assert selected == []

def test_bootstrap_resolves_authoritative_domain_even_when_metadata_tier_is_weak():
    people = ["Andrew Ng"]
    item = _item("Andrew Ng", "2026-09-30 10:00", "reuters")
    item["source"] = "Reuters"
    item["link"] = "https://www.reuters.com/technology/artificial-intelligence/andrew-ng-example/"
    item["source_tier"] = 3
    selected = bootstrap_candidates([item], people, seen_hashes=set())
    assert len(selected) == 1
    assert selected[0]["source_tier"] == 2
    assert selected[0]["people_bootstrap_source_tier"] == 2
    assert selected[0]["people_bootstrap_validated"] is True

