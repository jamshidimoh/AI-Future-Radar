"""Canonical interview-format evidence used across editorial and production routing.

This module deliberately separates format evidence from leader/watchlist identity.
Derived leader flags never count as interview evidence by themselves.
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


def _text(item):
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "description", "evidence_text")
    ).casefold()


def has_interview_evidence(item):
    """Return True only for format evidence, never for leader identity alone."""
    if not item:
        return False

    # Explicit collector/classifier evidence is authoritative.
    for key in ("interview_signal", "interview_format", "is_interview"):
        value = item.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip().casefold() in {"true", "yes", "1", "interview"}:
            return True

    content_type = str(item.get("content_type") or "").strip().casefold()
    if content_type in INTERVIEW_CONTENT_TYPES:
        return True

    # Textual format evidence is accepted only from inherently interview-oriented
    # media. This prevents a Google News article that merely mentions an interview
    # from becoming protected content.
    source_type = str(item.get("source_type") or "").strip().casefold()
    if source_type in _VIDEO_SOURCE_TYPES:
        return any(term in _text(item) for term in _INTERVIEW_TERMS)

    return False
