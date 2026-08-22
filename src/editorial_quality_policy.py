"""Single source of truth for production editorial quality gates."""
from __future__ import annotations

import re

TITLE_PERSIAN_RATIO_MIN = 0.25
BODY_PERSIAN_RATIO_MIN = 0.60
SUMMARY_MIN_CHARS = 180
WHY_MIN_CHARS = 140
SHORT_SOURCE_SUMMARY_MIN_CHARS = 120
SHORT_SOURCE_WHY_MIN_CHARS = 100
NORMAL_SCORE_TOLERANCE = 10.0
NORMAL_SCORE_FLOOR = 85.0
TITLE_MAX_CHARS = 160
LATIN_TOKEN_MAX_CHARS = 64
_BIDI_CONTROLS = "\u202A\u202B\u202C\u202D\u202E\u2066\u2067\u2069\u200E\u200F"
_LTR_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9._+/#:&'’()\-]*")
_URL_RE = re.compile(r"https?://[^\s<>\"]+")


def persian_ratio(text: str) -> float:
    letters = re.findall(r"[A-Za-z\u0600-\u06FF]", text or "")
    if not letters:
        return 0.0
    return sum("\u0600" <= c <= "\u06FF" for c in letters) / len(letters)


def news_language_ok(title: str, summary: str, why_it_matters: str) -> bool:
    return (
        persian_ratio(title) >= TITLE_PERSIAN_RATIO_MIN
        and persian_ratio(summary) >= BODY_PERSIAN_RATIO_MIN
        and persian_ratio(why_it_matters) >= BODY_PERSIAN_RATIO_MIN
    )


def length_ok(summary: str, why_it_matters: str, source_text: str) -> bool:
    source_len = len((source_text or "").strip())
    summary_len = len((summary or "").strip())
    why_len = len((why_it_matters or "").strip())
    if source_len < 350:
        return summary_len >= SHORT_SOURCE_SUMMARY_MIN_CHARS and why_len >= SHORT_SOURCE_WHY_MIN_CHARS
    return summary_len >= SUMMARY_MIN_CHARS and why_len >= WHY_MIN_CHARS


def headline_quality_ok(title: str) -> bool:
    value = str(title or "").strip()
    if not value or len(value) > TITLE_MAX_CHARS:
        return False
    if value.endswith(("...", "…", "!!!", "؟؟؟")):
        return False
    if re.search(r"\b(?:BREAKING|SHOCKING|MUST SEE|WOW)\b", value, re.I):
        return False
    if re.search(r"(.)\1\1\1", value):
        return False
    return True


def terminology_safety_ok(text: str) -> bool:
    value = str(text or "")
    if any(ch in value for ch in _BIDI_CONTROLS):
        return False
    for token in _LTR_TOKEN_RE.findall(value):
        if len(token) > LATIN_TOKEN_MAX_CHARS and not _URL_RE.match(token):
            return False
    return True


def editorial_fields_ok(title: str, summary: str, why_it_matters: str) -> bool:
    return (
        headline_quality_ok(title)
        and terminology_safety_ok(title)
        and terminology_safety_ok(summary)
        and terminology_safety_ok(why_it_matters)
    )


def normal_score_allowed(score: float, previous_score: float | None) -> bool:
    """Allow controlled step-downs without allowing an impossible stale floor.

    The previous published normal score remains the adaptive anchor. When the
    baseline itself is below the nominal floor, the same relative tolerance is
    applied to that baseline rather than imposing a hard 85-point cutoff.
    """
    if previous_score is None:
        return True
    previous = float(previous_score)
    threshold = max(NORMAL_SCORE_FLOOR, previous - NORMAL_SCORE_TOLERANCE) if previous >= NORMAL_SCORE_FLOOR else previous - NORMAL_SCORE_TOLERANCE
    return float(score) >= threshold
