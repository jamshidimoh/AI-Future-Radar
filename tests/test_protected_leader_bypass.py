import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from main import _annotate_named_leader_interviews, _split_protected
from src.editorial import filter_ai_relevance


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
