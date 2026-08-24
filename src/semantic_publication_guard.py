"""Cross-language publication conflict helpers shared by ranking and delivery."""
from __future__ import annotations

import re

_MIN_SHARED_ANCHORS = 3
_GENERIC_ANCHORS = {
    "ai", "artificial", "intelligence", "research", "study", "technology", "tech",
    "future", "new", "launch", "launches", "company", "project", "program", "course",
    "model", "platform", "system", "initiative", "development", "education", "health",
    "healthcare", "scientific", "science", "analysis", "discusses", "discussion",
    "support", "backs", "investment", "investing",
}
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize_digits(value: str) -> str:
    return str(value or "").translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)


def _anchors(value: str) -> set[str]:
    text = _normalize_digits(value)
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*|\d+(?:\.\d+)?", text)
    normalized = {re.sub(r"[-_]", "", token).lower() for token in tokens}
    return {x for x in normalized if (len(x) >= 3 or x.isdigit()) and x not in _GENERIC_ANCHORS}


def shared_anchor_count(left: str, right: str) -> int:
    return len(_anchors(left) & _anchors(right))


def cross_language_anchor_conflict(left: str, right: str) -> bool:
    """Detect a likely same-story rewrite across Persian/English variants."""
    return shared_anchor_count(left, right) >= _MIN_SHARED_ANCHORS
