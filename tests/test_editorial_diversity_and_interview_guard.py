from period_ranked_pipeline import _eligibility_split
from src.publication_guard import check_before_publish
from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio


def _item(title, source, score, *, category, content_type="news", tier=1, interview_signal=False):
    return {
        "title": title,
        "source": source,
        "source_tier": tier,
        "category": category,
        "content_type": content_type,
        "final_editorial_score": score,
        "interview_signal": interview_signal,
    }


def test_normal_portfolio_keeps_ai_convergence_and_mind_distinct():
    candidates = [
        _item("Frontier AI model capability", "OpenAI", 100, category="ai"),
        _item("Second frontier AI model", "Anthropic", 99, category="ai"),
        _item("Robotics breakthrough", "MIT CSAIL", 90, category="robotics", content_type="research"),
        _item("New consciousness study linked to AI", "Nature", 84, category="mind", content_type="research"),
        _item("AI governance future", "NIST", 70, category="future"),
    ]
    contract = load_editorial_contract()
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    areas = [x["mission_area"] for x in selected]
    assert "ai_core" in areas
    assert "convergence" in areas
    assert "mind_cognition" in areas
    assert len(set(areas)) == len(areas)


def test_verified_leader_interview_enters_protected_pool():
    interview = {
        "leader": "Anil Seth",
        "watch_person": "Anil Seth",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "content_type": "interview",
        "interview_signal": True,
        "source": "Major Interview Publisher",
        "source_tier": 2,
        "title": "Anil Seth interview on consciousness and AI",
        "summary": "A substantive conversation about consciousness, neuroscience and artificial intelligence.",
        "published": "2026-09-14T07:00:00Z",
        "discovery_query": "Anil Seth AI consciousness interview",
        "leader_signal_classification": {"interview": True, "context": True},
    }
    protected, regular = _eligibility_split([interview], max_protected=2)
    assert len(protected) == 1
    assert protected[0]["protected_content"] is True
    assert regular == []


def test_same_entity_distinct_event_stays_publishable(tmp_path):
    ledger = tmp_path / "telegram_feedback.json"
    ledger.write_text(
        '{"version":2,"messages":{"1":{"title":"Sam Altman discusses an OpenAI model introduction in Washington","summary":"OpenAI introduced a new model during Sam Altman\'s Washington visit.","link":"https://example.com/old"}}}',
        encoding="utf-8",
    )
    import src.publication_guard as pg
    pg.LEDGER_PATH = ledger
    text = "<b>📡 Sam Altman says OpenAI going public in 2026 would be ill-advised</b>\n<blockquote>📌 <b>خلاصه</b>\nSam Altman said taking OpenAI public in 2026 would be ill-advised.</blockquote>"
    allowed, _ = check_before_publish(text, "https://example.com/new")
    assert allowed



def test_priority_people_lane_prefers_newest_substantive_story_over_higher_score_old_story():
    from period_ranked_pipeline import _priority_story_diversified

    old = _item("Older Sam Altman interview", "Major Interview Publisher", 99, category="ai", content_type="interview", tier=1, interview_signal=True)
    old.update({
        "leader": "Sam Altman",
        "watch_person": "Sam Altman",
        "is_leader_watch": True,
        "priority_story_people": ["sam altman"],
        "published": "2026-09-15T10:00:00Z",
        "signal_score": 90,
        "leader_source_authority": 10,
    })
    new = _item("Newest Sam Altman interview", "Major Interview Publisher", 82, category="ai", content_type="interview", tier=1, interview_signal=True)
    new.update({
        "leader": "Sam Altman",
        "watch_person": "Sam Altman",
        "is_leader_watch": True,
        "priority_story_people": ["sam altman"],
        "published": "2026-09-21T18:00:00Z",
        "signal_score": 70,
        "leader_source_authority": 10,
    })
    selected = _priority_story_diversified([old, new])
    assert [x["title"] for x in selected] == ["Newest Sam Altman interview"]


def test_priority_people_lane_orders_different_people_by_freshness_not_person_priority():
    from period_ranked_pipeline import _priority_story_diversified

    old = _item("Old Demis Hassabis interview", "Publisher A", 99, category="ai", content_type="interview", tier=1, interview_signal=True)
    old.update({"leader": "Demis Hassabis", "watch_person": "Demis Hassabis", "priority_story_people": ["demis hassabis"], "published": "2026-09-15T10:00:00Z", "leader_source_authority": 10})
    new = _item("New Yann LeCun interview", "Publisher B", 80, category="ai", content_type="interview", tier=1, interview_signal=True)
    new.update({"leader": "Yann LeCun", "watch_person": "Yann LeCun", "priority_story_people": ["yann lecun"], "published": "2026-09-21T18:00:00Z", "leader_source_authority": 9})
    selected = _priority_story_diversified([old, new])
    assert selected[0]["title"] == "New Yann LeCun interview"
