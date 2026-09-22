from pathlib import Path

from src.people_watch import bootstrap_candidates, build_bootstrap_state, deduplicate_people_signals, load_people_watchlist, post_bootstrap_candidates


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


def test_people_dedup_removes_exact_duplicate_identity_but_keeps_independent_signals():
    items = [
        _item("Sam Altman", "2026-09-22 10:00", "same", title_suffix="A"),
        _item("Sam Altman", "2026-09-22 10:00", "same", title_suffix="A"),
        _item("Sam Altman", "2026-09-22 11:00", "independent", title_suffix="B"),
    ]
    selected = deduplicate_people_signals(items, seen_signatures=[])
    assert len(selected) == 2
    assert {item["link"] for item in selected} == {
        "https://example.com/same",
        "https://example.com/independent",
    }


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
