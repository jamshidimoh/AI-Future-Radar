"""Canonical interview-format evidence used across editorial and production routing.

Interview format is classified once here and consumed by editorial/production.
Leader/watchlist identity is context, not evidence by itself; however, a verified
leader-watch item with an interview content type is valid format evidence when the
source is not an unverified Google News aggregation label.
"""

INTERVIEW_CONTENT_TYPES = frozenset({
    "interview", "podcast", "talk", "lecture", "fireside",
    "conversation", "discussion", "q&a",
})

_INTERVIEW_TERMS = (
    "interview", "conversation", "fireside", "q&a", "question and answer",
    "talk with", "talks with", "speaks with", "in conversation", "sits down with",
    "مصاحبه", "گفتگو", "گفت‌وگو", "پرسش و پاسخ",
)

_VIDEO_SOURCE_TYPES = frozenset({"youtube", "video", "podcast"})


def _contains_interview_term(value):
    text = str(value or "").casefold()
    return any(term in text for term in _INTERVIEW_TERMS)


def _text(item):
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "description", "evidence_text")
    ).casefold()


def _is_google_news_aggregation(item):
    values = (
        str(item.get("source_type") or ""),
        str(item.get("source") or ""),
        str(item.get("canonical_url") or ""),
    )
    text = " ".join(values).casefold()
    return "google news" in text or "news.google.com" in text


def _has_verified_leader_context(item):
    name = str(item.get("leader") or item.get("watch_person") or "").strip()
    return bool(
        name
        and (
            item.get("is_leader_watch")
            or item.get("leader_watch_protected")
            or item.get("leader_signal")
        )
    )


def has_interview_evidence(item):
    """Return True for canonical format evidence with source/provenance safeguards."""
    if not item:
        return False

    for key in ("interview_signal", "interview_format", "is_interview"):
        value = item.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip().casefold() in {"true", "yes", "1", "interview"}:
            return True

    # Explicit format in the title is strong evidence regardless of source.
    if _contains_interview_term(item.get("title")):
        return True

    content_type = str(item.get("content_type") or "").strip().casefold()

    # A verified leader-watch item classified upstream as an interview is valid
    # format evidence, except when the only provenance is a Google News aggregation.
    # This preserves the established leader-priority contract without allowing
    # generic Google News labels to create false protected interviews.
    if (
        content_type in INTERVIEW_CONTENT_TYPES
        and _has_verified_leader_context(item)
        and not _is_google_news_aggregation(item)
    ):
        return True

    source_type = str(item.get("source_type") or "").strip().casefold()
    source = str(item.get("source") or "").strip().casefold()
    interview_media = source_type in _VIDEO_SOURCE_TYPES or any(
        token in source for token in ("youtube", "podcast", "spotify")
    )
    if interview_media and (
        content_type in INTERVIEW_CONTENT_TYPES
        or _contains_interview_term(_text(item))
    ):
        return True

    # Generic content_type=interview without trustworthy provenance is not enough.
    return False
