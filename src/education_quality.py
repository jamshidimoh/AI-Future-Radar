"""Deterministic quality gates for source-grounded educational lessons."""
from __future__ import annotations

import re
from typing import Any

from education_source_policy import validate_current_sources

# Common Persian transliterations that must never survive the final education draft.
BANNED_TRANSLITERATIONS = {
    "پلی‌کریسیس", "پلی کریسیس", "پلی‌تونی‌تی", "پلی تونی تی",
    "دمیس هاسابیس", "جفری هینتون", "یوئن یوئن آنگ", "یوئن یوئن انگ",
    "سم آلتمن", "یان لوکان", "یان لکون", "ایلیا سوتسکور",
}

REQUIRED_FIELDS = (
    "term_a_definition", "term_a_simple", "term_b_definition", "term_b_simple",
    "relationship", "example", "takeaway",
)


def source_quality(source: dict[str, Any]) -> int:
    """Return authority score supplied by the shared source-governance policy."""
    try:
        return int(source.get("authority_score", 0))
    except (TypeError, ValueError):
        return 0


def validate_sources(sources: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]], str]:
    """Require two current, independently attributable sources with authority support."""
    return validate_current_sources(sources)


def terminology_errors(item: dict[str, Any]) -> list[str]:
    text = " ".join(str(item.get(k, "")) for k in REQUIRED_FIELDS)
    errors = [x for x in BANNED_TRANSLITERATIONS if x in text]
    phonetic_patterns = ("کدنویسی وایب", "وایب کدینگ", "لوپ انجینیرینگ", "مهندسی کانتکست")
    errors.extend(x for x in phonetic_patterns if x in text)
    return sorted(set(errors))


def educational_quality_score(item: dict[str, Any], sources: list[dict[str, Any]]) -> tuple[int, list[str]]:
    issues: list[str] = []
    for field in REQUIRED_FIELDS:
        if not str(item.get(field, "")).strip():
            issues.append(f"missing:{field}")
    for field in REQUIRED_FIELDS:
        text = str(item.get(field, ""))
        if len(text) < 20:
            issues.append(f"too_short:{field}")
    if terminology_errors(item):
        issues.append("terminology")
    if not str(item.get("example", "")).strip():
        issues.append("no_example")
    if not str(item.get("relationship", "")).strip():
        issues.append("no_relationship")
    source_ok, _, reason = validate_sources(sources)
    if not source_ok:
        issues.append(f"source:{reason}")

    score = 100
    score -= min(60, len([x for x in issues if x.startswith("missing:") or x.startswith("too_short:")]) * 8)
    if "terminology" in issues:
        score -= 15
    if any(x.startswith("source:") for x in issues):
        score -= 25
    return max(0, score), issues


def assert_publishable(item: dict[str, Any], sources: list[dict[str, Any]], minimum_score: int = 85) -> list[dict[str, Any]]:
    score, issues = educational_quality_score(item, sources)
    if issues or score < minimum_score:
        raise RuntimeError(f"[Education QA] REJECT score={score} issues={','.join(issues) or 'none'}")
    ok, verified, reason = validate_sources(sources)
    if not ok:
        raise RuntimeError(f"[Education Source QA] REJECT {reason}")
    return verified
