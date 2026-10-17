"""Regression tests for keeping normal leader news out of interview-only People routing."""

import production_entrypoint as entry
from src import dedup


def _non_interview_people_signal():
    return {
        "title": "Elorian introduces Glimpse, a model that understands images",
        "summary": "The company introduced a multimodal model for image understanding.",
        "why_it_matters": "It adds a concrete multimodal capability to the current AI product landscape.",
        "content_type": "news",
        "category": "ai",
        "source": "Publisher",
        "source_tier": 1,
        "people_lane": True,
        "final_editorial_score": 64.0,
        "editorial_score": 64.0,
        "signal_score": 0.0,
        "evidence_strength": 4.0,
        "published": "2026-10-17T06:00:00Z",
        "link": "https://publisher.example/glimpse",
    }


def test_non_interview_people_signal_is_reclassified_for_normal_gates():
    item = _non_interview_people_signal()

    assert entry._normalize_people_lane_role(item) is True
    assert item["people_lane"] is False
    assert item["_people_lane_reclassified_to_normal"] is True
    assert entry._normalize_people_lane_role(item) is False


def test_substantive_priority_interview_keeps_people_role():
    item = {
        "title": "Christof Koch on consciousness and neurotechnology",
        "summary": (
            "A substantive interview about consciousness, brain-computer interfaces, "
            "neurotechnology, evidence, limitations, and the next research questions."
        ),
        "why_it_matters": "It presents the expert's own view and explains the evidence behind it.",
        "content_type": "interview",
        "source": "Lex Fridman Podcast",
        "source_tier": 1,
        "leader": "Christof Koch",
        "watch_person": "Christof Koch",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "interview_evidence": {"explicit": True},
        "people_lane": True,
        "final_editorial_score": 65.0,
    }

    assert entry._normalize_people_lane_role(item) is False
    assert item["people_lane"] is True


def test_people_bootstrap_role_is_never_reclassified():
    item = {
        **_non_interview_people_signal(),
        "people_bootstrap": True,
        "people_bootstrap_validated": True,
    }

    assert entry._normalize_people_lane_role(item) is False
    assert item["people_lane"] is True


def test_non_interview_people_signal_returns_to_normal_portfolio(monkeypatch):
    monkeypatch.setattr(dedup, "load_source_history", lambda: [])
    monkeypatch.setattr(dedup, "load_seen", lambda: (set(), []))
    monkeypatch.setattr(
        entry,
        "select_regular_portfolio",
        lambda candidates, **kwargs: list(candidates)[:kwargs.get("max_posts", 1)],
    )

    selected = entry._unified_portfolio_select(
        [_non_interview_people_signal()],
        max_posts=3,
        policy={"leader_protected_max": 1, "replacement_buffer": 3},
        bootstrap_mode=False,
    )

    assert len(selected) == 1
    assert selected[0]["people_lane"] is False
    assert selected[0]["_people_lane_reclassified_to_normal"] is True
    assert selected[0]["normal_period_rank"] == 1
    assert selected[0]["period_rank"] == 1
