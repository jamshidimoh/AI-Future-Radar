from src.priority_people import is_substantive_priority_interview, priority_people_features


def test_tier0_rank_is_not_a_classification_signal():
    item = {
        "title": "Nick Bostrom’s Superintelligence - Medium",
        "content_type": "article",
        "summary": "A long analytical article about the book and its ideas, without a direct interview or attributable quote.",
        "source": "Medium",
        "tier0_rank": 1,
    }
    people, tier0, bonus = priority_people_features(item)
    assert "nick bostrom" in people
    assert tier0 is False
    assert bonus == 0.0
    assert is_substantive_priority_interview(item) is False


def test_explicit_priority_interview_remains_tier0():
    item = {
        "title": "Interview with Nick Bostrom about superintelligence",
        "content_type": "interview",
        "summary": "Nick Bostrom discusses superintelligence, alignment, long-term AI risks, and the future of advanced AI systems.",
        "source": "Specialist podcast",
    }
    people, tier0, bonus = priority_people_features(item)
    assert "nick bostrom" in people
    assert tier0 is True
    assert bonus == 50.0


def test_blocked_candidate_cannot_use_tier0_exemption():
    item = {
        "title": "Interview with Nick Bostrom about superintelligence",
        "content_type": "interview",
        "summary": "Nick Bostrom discusses superintelligence, alignment, long-term AI risks, and the future of advanced AI systems.",
        "source": "Specialist podcast",
        "_publication_blocked": True,
    }
    people, tier0, bonus = priority_people_features(item)
    assert people == []
    assert tier0 is False
    assert bonus == 0.0
    assert is_substantive_priority_interview(item) is False
