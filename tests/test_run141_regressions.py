from period_ranked_pipeline import _eligibility_split


def test_leader_activity_does_not_enter_regular_ai_gate():
    item = {
        "leader": "Sam Altman",
        "watch_person": "Sam Altman",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "leader_activity_signal": True,
        "content_type": "product_news",
        "title": "Sam Altman announces a new initiative",
        "summary": "A leadership update without literal AI terminology in the headline.",
        "source": "Google News (example)",
        "source_tier": 1,
    }
    protected, regular = _eligibility_split([item], max_protected=2)
    assert len(protected) == 1
    assert regular == []
    assert protected[0]["protected_content"] is True
    assert protected[0]["protected_reason"] == "leader_interview_or_activity"
