from src.priority_people import is_substantive_priority_interview


def test_ranked_tier0_marker_does_not_create_tier0_after_rendering():
    item = {
        "tier0_rank": 1,
        "period_rank": 1,
        "normal_period_rank": None,
        "content_type": "news",
        "title": "AMD buys AI chip startup",
        "summary": "ترجمه و خلاصه نهایی پس از رتبه‌بندی تغییر کرده است.",
    }
    assert is_substantive_priority_interview(item) is False


def test_unmarked_normal_story_is_not_forced_into_tier0():
    item = {
        "period_rank": 3,
        "normal_period_rank": 1,
        "content_type": "news",
        "title": "یک خبر عادی فناوری",
        "summary": "این یک خبر عادی بدون فرد اولویت‌دار است.",
    }
    assert is_substantive_priority_interview(item) is False


def test_actual_priority_interview_remains_tier0():
    item = {
        "title": "Interview with Sam Altman about frontier AI",
        "content_type": "interview",
        "summary": "Sam Altman discusses frontier models, agents, safety and the future of AI systems.",
    }
    assert is_substantive_priority_interview(item) is True
