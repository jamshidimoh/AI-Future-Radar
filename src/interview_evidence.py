"""Canonical interview-format evidence used across editorial and production routing.

This module separates format evidence from leader/watchlist identity. Derived leader
flags and generic content-type labels alone never count as interview evidence.
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


def has_interview_evidence(item):
    """Return True only for format evidence, never for leader identity alone."""
    if not item:
        return False

    for key in ("interview_signal", "interview_format", "is_interview"):
        value = item.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip().casefold() in {"true", "yes", "1", "interview"}:
            return True

    # A title that explicitly identifies the format is usable evidence regardless
    # of source. This preserves Persian/English interview titles during exhaustion
    # without treating a generic article as protected.
    if _contains_interview_term(item.get("title")):
        return True

    source_type = str(item.get("source_type") or "").strip().casefold()
    source = str(item.get("source") or "").strip().casefold()
    interview_media = source_type in _VIDEO_SOURCE_TYPES or any(
        token in source for token in ("youtube", "podcast", "spotify")
    )
    if interview_media and (
        str(item.get("content_type") or "").strip().casefold() in INTERVIEW_CONTENT_TYPES
        or _contains_interview_term(_text(item))
    ):
        return True

    # Generic news/content-type labels are supporting metadata only; by themselves
    # they are insufficient because upstream/news classifiers can over-label articles.
    return False
