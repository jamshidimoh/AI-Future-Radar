import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from main import _annotate_named_leader_interviews, _split_protected
from src.editorial import filter_ai_relevance
from src.story_identity import deduplicate_stories


def test_named_leader_recovered_before_filter():
    items = [{
        "title": "Dario Amodei in conversation about the future of AI",
        "summary": "Discussion of safety, models and the next generation of AI with enough context for a substantive interview.",
        "category": "future",
        "source": "Independent Interview Podcast",
        "content_type": "podcast",
        "source_tier": 3,
    }]
    _annotate_named_leader_interviews(items, ["Sam Altman", "Dario Amodei"])
    assert items[0]["watch_person"] == "Dario Amodei"
    assert items[0]["leader"] == "Dario Amodei"
    assert items[0]["_named_leader_interview"] is True
    protected, regular = _split_protected(items)
    assert len(protected) == 1
    assert len(regular) == 0


def test_protected_leader_bypasses_regular_ai_gate():
    item = {
        "title": "Jensen Huang interview on AI and robotics",
        "summary": "An interview about future AI infrastructure and robotics with substantial technical context.",
        "category": "quantum",
        "source": "Generic Source",
        "content_type": "interview",
        "source_tier": 3,
    }
    _annotate_named_leader_interviews([item], ["Jensen Huang"])
    protected, regular = _split_protected([item])
    assert len(protected) == 1
    assert not regular
    assert filter_ai_relevance(regular, ["AI", "agent", "AGI"]) == []
    assert protected[0]["protected_reason"] == "leader_interview_or_activity"


def test_distinct_protected_leader_interview_survives_similar_history():
    candidate = {
        "title": "Dario Amodei discusses AI safety and frontier models in a new conversation",
        "summary": "A new interview covering AI safety, frontier models, scaling and future systems.",
        "description": "Extended discussion with Dario Amodei.",
        "leader": "Dario Amodei",
        "watch_person": "Dario Amodei",
        "protected_content": True,
        "protected_reason": "leader_interview_or_activity",
        "interview_signal": True,
        "canonical_url": "https://example.com/interview-new",
    }
    prior = {
        "title": "Dario Amodei discusses AI safety and frontier models in an earlier conversation",
        "summary": "An interview covering AI safety, frontier models, scaling and future systems.",
        "leader": "Dario Amodei",
        "canonical_url": "https://example.com/interview-old",
    }
    result = deduplicate_stories([candidate], history=[prior])
    assert result == [candidate]


def test_exact_duplicate_protected_leader_interview_is_still_removed():
    candidate = {
        "title": "Dario Amodei in conversation about frontier AI",
        "leader": "Dario Amodei",
        "protected_content": True,
        "protected_reason": "leader_interview_or_activity",
        "interview_signal": True,
        "canonical_url": "https://example.com/interview-1",
    }
    prior = dict(candidate)
    assert deduplicate_stories([candidate], history=[prior]) == []
