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
    "این خبر نشان می‌دهد", "این موضوع نشان می‌دهد", "این پیشرفت می‌تواند", "این فناوری می‌تواند",
    "اهمیت این خبر در این است", "در آینده می‌تواند", "می‌تواند آینده هوش مصنوعی را تغییر دهد",
    "گامی مهم در مسیر", "اهمیت زیادی دارد",
)
_IMPACT_MARKERS = (
    "باعث", "منجر", "امکان", "کاهش", "افزایش", "بهبود", "تغییر", "پیامد", "ریسک", "هزینه", "دقت",
    "سرعت", "کاربرد", "استقرار", "ارزیابی", "محدودیت", "مزیت", "اثر", "رقابت", "بازار", "پژوهش",
    "سیاست", "حکمرانی",
)
_SPECIFICITY_MARKERS = (
    "مدل", "روش", "آزمایش", "نتیجه", "داده", "معماری", "عامل", "آموزش", "استنتاج", "ارزیابی", "معیار",
    "پژوهش", "مقاله", "سیستم", "کد", "ربات", "کوانتوم", "ژنوم", "پروتئین", "آگاهی", "شناخت", "AGI",
    "LLM", "AI", "RL", "SFT", "DPO", "RAG",
)
_GENERIC_WORDS = {"این", "آن", "برای", "در", "از", "به", "با", "که", "و", "یک", "است", "شود", "دارد", "همین", "موضوع", "خبر", "فناوری", "پژوهش"}


def persian_ratio(text: str) -> float:
    letters = re.findall(r"[A-Za-z\u0600-\u06FF]", text or "")
    if not letters:
        return 0.0
    return sum("\u0600" <= c <= "\u06FF" for c in letters) / len(letters)


def news_language_ok(title: str, summary: str, why_it_matters: str) -> bool:
    return persian_ratio(title) >= TITLE_PERSIAN_RATIO_MIN and persian_ratio(summary) >= BODY_PERSIAN_RATIO_MIN and persian_ratio(why_it_matters) >= BODY_PERSIAN_RATIO_MIN


def length_ok(summary: str, why_it_matters: str, source_text: str) -> bool:
    source_len, summary_len, why_len = len((source_text or "").strip()), len((summary or "").strip()), len((why_it_matters or "").strip())
    if source_len < 350:
        return summary_len >= SHORT_SOURCE_SUMMARY_MIN_CHARS and why_len >= SHORT_SOURCE_WHY_MIN_CHARS
    return summary_len >= SUMMARY_MIN_CHARS and why_len >= WHY_MIN_CHARS


def _sentence_count(text: str) -> int:
    return len([p.strip() for p in re.split(r"(?<=[.!؟])\s+", str(text or "")) if p.strip()])


def _content_tokens(text: str) -> set[str]:
    value = str(text or "").lower()
    latin = {x for x in re.findall(r"[a-z][a-z0-9.+/#-]{1,}", value) if len(x) >= 2}
    persian = {x for x in re.findall(r"[\u0600-\u06ff]{3,}", value) if x not in _GENERIC_WORDS}
    return latin | persian


def _specificity_score(summary: str) -> int:
    value = str(summary or "")
    score = int(bool(re.search(r"\d", value))) + int(bool(re.search(r"\b[A-Z][A-Za-z0-9.+/#-]{1,}\b", value)))
    score += min(2, sum(1 for marker in _SPECIFICITY_MARKERS if marker.lower() in value.lower()))
    return score + int(bool(re.search(r"(?:در|با|روی|برای)\s+[\u0600-\u06ffA-Za-z]", value)))


def _overlap(a: str, b: str) -> float:
    left, right = _content_tokens(a), _content_tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def _source_support(summary: str, why: str, source_text: str) -> tuple[float, float]:
    source, summary_tokens, why_tokens = _content_tokens(source_text), _content_tokens(summary), _content_tokens(why)
    if not source:
        return 0.0, 0.0
    lexical_summary = len(summary_tokens & source) / max(1, len(summary_tokens))
    lexical_why = len(why_tokens & source) / max(1, len(why_tokens))
    source_anchors = set(re.findall(r"\d+(?:[.,]\d+)?%?", source_text or ""))
    source_anchors |= {x.lower() for x in re.findall(r"\b[A-Z][A-Za-z0-9.+/#-]{1,}\b", source_text or "") if len(x) >= 2}
    if source_anchors and persian_ratio(summary) >= BODY_PERSIAN_RATIO_MIN:
        def anchor_ratio(text: str) -> float:
            present = set(re.findall(r"\d+(?:[.,]\d+)?%?", text or ""))
            present |= {x.lower() for x in re.findall(r"\b[A-Z][A-Za-z0-9.+/#-]{1,}\b", text or "") if len(x) >= 2}
            return len(present & source_anchors) / max(1, len(present))
        anchor_summary, anchor_why = anchor_ratio(summary), anchor_ratio(why)
        if persian_ratio(source_text) < 0.35:
            summary_support = max(lexical_summary, anchor_summary * 0.55)
            # The why section is an editorial implication, not a translation of
            # the source. Permit only bounded evidence inherited from a strongly
            # supported summary and shared substantive terms; generic claims remain
            # blocked by the generic-why and impact-marker gates above.
            derived_why = _overlap(why, summary) * 0.50 if summary_support >= 0.12 else 0.0
            return summary_support, max(lexical_why, anchor_why * 0.35, derived_why)
    return lexical_summary, lexical_why


def editorial_value_ok(title: str, summary: str, why_it_matters: str, source_text: str = "") -> bool:
    summary, why, source = str(summary or "").strip(), str(why_it_matters or "").strip(), str(source_text or "").strip()
    source_len = len(source)
    if not summary or not why:
        return False
    if source_len >= 350 and (_sentence_count(summary) < 2 or _sentence_count(why) < 2):
        return False
    if _specificity_score(summary) < 3 or any(phrase in why for phrase in _GENERIC_WHY):
        return False
    if not any(marker in why for marker in _IMPACT_MARKERS) or _overlap(summary, why) >= 0.78:
        return False
    if len(summary) > 260 and len(summary) / max(1, source_len) < 0.06 and source_len >= 700:
        return False
    summary_support, why_support = _source_support(summary, why, source)
    if source_len >= 350:
        if persian_ratio(summary) >= BODY_PERSIAN_RATIO_MIN and persian_ratio(source) < 0.35:
            return summary_support >= 0.12 and why_support >= 0.04
        return summary_support >= 0.28 and why_support >= 0.16
    if source_len > 0:
        if persian_ratio(summary) >= BODY_PERSIAN_RATIO_MIN and persian_ratio(source) < 0.35:
            return summary_support >= 0.08 and why_support >= 0.03
        return summary_support >= 0.20 and why_support >= 0.10
    return True


def headline_quality_ok(title: str) -> bool:
    value = str(title or "").strip()
    return bool(value) and len(value) <= TITLE_MAX_CHARS and not value.endswith(("...", "…", "!!!", "؟؟؟")) and not re.search(r"\b(?:BREAKING|SHOCKING|MUST SEE|WOW)\b", value, re.I) and not re.search(r"(.)\1\1\1", value)


def terminology_safety_ok(text: str) -> bool:
    value = str(text or "")
    if any(ch in value for ch in _BIDI_CONTROLS):
        return False
    return all(len(token) <= LATIN_TOKEN_MAX_CHARS or _URL_RE.match(token) for token in _LTR_TOKEN_RE.findall(value))


def editorial_fields_ok(title: str, summary: str, why_it_matters: str) -> bool:
    return headline_quality_ok(title) and terminology_safety_ok(title) and terminology_safety_ok(summary) and terminology_safety_ok(why_it_matters)


def normal_score_allowed(score: float, previous_score: float | None) -> bool:
    if previous_score is None:
        return True
    previous = float(previous_score)
    threshold = max(NORMAL_SCORE_FLOOR, previous - NORMAL_SCORE_TOLERANCE) if previous >= NORMAL_SCORE_FLOOR else previous - NORMAL_SCORE_TOLERANCE
    return float(score) >= threshold
