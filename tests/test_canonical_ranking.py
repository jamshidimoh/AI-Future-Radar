import json

from period_ranked_pipeline import ranking
from src.priority_people import priority_people_features


def test_substantive_priority_interview_stays_tier0():
    item = {"title": "Mark Zuckerberg in conversation about the future of AI", "summary": "An extended interview explores Meta's AI strategy and the future of open models.", "description": "The conversation covers model development, agents, and long-term AI strategy.", "content_type": "interview", "source": "Podcast"}
    people, is_tier0, bonus = priority_people_features(item)
    assert "mark zuckerberg" in people
    assert is_tier0 is True
    assert bonus == 50.0


def test_protected_leader_capacity_demotes_overflow_candidates():
    items = [
        {"title": "Leader one on AI agents", "summary": "Interview about AI agents and frontier models.", "leader": "Elon Musk", "editorial_score": 90.0, "content_type": "interview", "leader_watch_protected": True},
        {"title": "Leader two on AI safety", "summary": "Interview about AI safety and model deployment.", "leader": "Sam Altman", "editorial_score": 89.0, "content_type": "interview", "leader_watch_protected": True},
        {"title": "Leader three on AI infrastructure", "summary": "Interview about AI infrastructure and accelerated computing.", "leader": "Jensen Huang", "editorial_score": 88.0, "content_type": "interview", "leader_watch_protected": True},
    ]
    selected, regular = ranking._eligibility_split(items, max_protected=2)
    assert len(selected) == 2
    assert all(item.get("protected_slot") is True for item in selected)
    assert len(regular) == 1
    assert regular[0].get("protected_slot") is False
    assert regular[0].get("protected_content") is False
    assert regular[0].get("_rank_is_tier0") is False
