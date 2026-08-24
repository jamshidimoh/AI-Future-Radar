"""Regression checks for protected leader interview routing."""

from main import _is_protected_leader_interview


def test_google_news_mention_is_not_protected_without_interview_evidence():
    item = {
        "leader": "Christof Koch",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "content_type": "interview",
        "source": "Google News (example)",
        "title": "Christof Koch, a Pioneer of Consciousness Research, Questions Whether the Brain Truly Creates Consciousness",
        "canonical_url": "https://news.google.com/rss/articles/example",
    }
    assert _is_protected_leader_interview(item) is False


def test_explicit_interview_evidence_remains_protected():
    item = {
        "leader": "Christof Koch",
        "is_leader_watch": True,
        "leader_watch_protected": True,
        "_named_leader_interview": True,
        "content_type": "interview",
        "source": "Google News (example)",
        "title": "Christof Koch interview: consciousness, brain science and AI",
        "canonical_url": "https://news.google.com/rss/articles/example2",
    }
    assert _is_protected_leader_interview(item) is True
