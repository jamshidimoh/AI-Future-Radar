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
_GENERIC_WHY = (
    "این خبر نشان می‌دهد",
    "این موضوع نشان می‌دهد",
    "این پیشرفت می‌تواند",
    "این فناوری می‌تواند",
    "اهمیت این خبر در این است",
    "در آینده می‌تواند",
    "می‌تواند آینده هوش مصنوعی را تغییر دهد",
    "گامی مهم در مسیر",
    "اهمیت زیادی دارد",
)
_IMPACT_MARKERS = (
    "باعث", "منجر", "امکان", "کاهش", "افزایش", "بهبود", "تغییر", "پیامد", "ریسک",
    "هزینه", "دقت", "سرعت", "کاربرد", "استقرار", "ارزیابی", "محدودیت", "مزیت",
    "اثر", "رقابت", "بازار", "پژوهش", "سیاست", "حکمرانی",
)
_SPECIFICITY_MARKERS = (
    "مدل", "روش", "آزمایش", "نتیجه", "داده", "معماری", "عامل", "آموزش", "استنتاج",
    "ارزیابی", "معیار", "پژوهش", "مقاله", "سیستم", "کد", "ربات", "کوانتوم", "ژنوم",
    "پروتئین", "آگاهی", "شناخت", "AGI", "LLM", "AI", "RL", "SFT", "DPO", "RAG",
)


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


def _sentence_count(text: str) -> int:
    parts = [p.strip() for p in re.split(r"(?<=[.!؟])\s+", str(text or "")) if p.strip()]
    return len(parts)


def _content_tokens(text: str) -> set[str]:
    value = str(text or "").lower()
    latin = {x for x in re.findall(r"[a-z][a-z0-9.+/#-]{1,}", value) if len(x) >= 2}
    persian = {x for x in re.findall(r"[\u0600-\u06ff]{3,}", value) if x not in {"است", "این", "برای", "شود", "دارد", "همین"}}
    return latin | persian


def _specificity_score(summary: str) -> int:
    value = str(summary or "")
    score = 0
    if re.search(r"\d", value):
        score += 1
    if re.search(r"\b[A-Z][A-Za-z0-9.+/#-]{1,}\b", value):
        score += 1
    lower = value.lower()
    score += min(2, sum(1 for marker in _SPECIFICITY_MARKERS if marker.lower() in lower))
    if re.search(r"(?:در|با|روی|برای)\s+[\u0600-\u06ffA-Za-z]", value):
        score += 1
    return score


def _overlap(a: str, b: str) -> float:
    left, right = _content_tokens(a), _content_tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def editorial_value_ok(title: str, summary: str, why_it_matters: str, source_text: str = "") -> bool:
    """Reject fluent-but-empty News copy while leaving source/ranking/publish paths untouched.

    This is intentionally deterministic: it checks informativeness, distinctness and
    concrete impact markers without attempting to judge factuality with another LLM.
    """
    summary = str(summary or "").strip()
    why = str(why_it_matters or "").strip()
    source_len = len(str(source_text or "").strip())
    if not summary or not why:
        return False
    if source_len >= 350 and _sentence_count(summary) < 2:
        return False
    if source_len >= 350 and _sentence_count(why) < 2:
        return False
    if _specificity_score(summary) < 3:
        return False
    if any(phrase in why for phrase in _GENERIC_WHY):
        return False
    if not any(marker in why for marker in _IMPACT_MARKERS):
        return False
    if _overlap(summary, why) >= 0.78:
        return False
    if len(summary) > 260 and len(summary) / max(1, source_len) < 0.06 and source_len >= 700:
        return False
    return True


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
