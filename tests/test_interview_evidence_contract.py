from interview_evidence import has_interview_evidence
from main import _is_protected_leader_interview


def test_google_news_content_type_alone_is_not_interview_evidence():
    item = {
        "content_type": "interview",
        "source": "Google News",
        "title": "Christof Koch discusses consciousness research",
    }
    assert has_interview_evidence(item) is False


def test_english_interview_title_is_explicit_evidence():
    item = {
        "content_type": "interview",
        "source": "Google News",
        "title": "Christof Koch interview: consciousness, brain science and AI",
    }
    assert has_interview_evidence(item) is True


def test_persian_interview_title_survives_as_explicit_evidence():
    item = {
        "content_type": "interview",
        "source": "YouTube",
        "source_type": "youtube",
        "title": "مصاحبه با کریستف کخ درباره آگاهی و هوش مصنوعی",
    }
    assert has_interview_evidence(item) is True


def test_derived_leader_flags_do_not_create_interview_evidence():
    item = {
        "leader": "Christof Koch",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "content_type": "interview",
        "source": "Google News",
        "title": "Christof Koch discusses consciousness research",
    }
    assert _is_protected_leader_interview(item) is False
