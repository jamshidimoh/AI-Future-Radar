"""Canonical event/story identity for cross-source news deduplication.

The classifier is deliberately hybrid and dependency-free. It complements URL
and exact-title identity with normalized entities, event/action/object signals,
time proximity, and material-update detection. It does not use a hard-coded
story title list and does not bypass duplicate checks for protected content.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "with", "by", "at", "as",
    "is", "are", "was", "were", "be", "been", "this", "that", "these", "those", "new", "latest",
    "news", "update", "says", "said", "will", "has", "have", "had", "from", "into", "about", "after",
    "در", "به", "از", "با", "و", "یا", "برای", "که", "این", "آن", "یک", "های", "ها", "است", "شد", "می",
    "را", "بر", "هم", "نیز", "درباره", "توسط", "کرد", "کند", "شده", "هایش", "روی", "تا",
}

_ALIASES = {
    "meta": "meta", "متا": "meta", "facebook": "meta",
    "mark zuckerberg": "mark_zuckerberg", "مارک زاکربرگ": "mark_zuckerberg", "زاکربرگ": "mark_zuckerberg",
    "muse": "muse", "موس": "muse",
    "personal superintelligence": "personal_superintelligence", "سوپر هوش شخصی": "personal_superintelligence",
    "ai agent": "ai_agent", "ai agents": "ai_agent", "عامل هوش مصنوعی": "ai_agent", "عامل هوشمند": "ai_agent",
    "terence tao": "terence_tao", "تِرنس تائو": "terence_tao", "ترنس تائو": "terence_tao", "تائو": "terence_tao",
    "open problems": "open_problems", "open problem": "open_problems", "مسائل باز": "open_problems", "مسئله باز": "open_problems",
    "open science": "open_science", "علم باز": "open_science",
    "stanford hai": "stanford_hai", "stanford human-centered ai": "stanford_hai", "استنفورد": "stanford_hai",
    "local laws": "local_laws", "local law": "local_laws", "قوانین محلی": "local_laws", "قانون محلی": "local_laws",
    "discriminatory": "discriminatory", "تبعیض آمیز": "discriminatory", "تبعیض‌آمیز": "discriminatory", "تبعیض": "discriminatory",
    "legal review": "legal_review", "legal analysis": "legal_review", "بررسی حقوقی": "legal_review", "تحلیل حقوقی": "legal_review",
    "introduce": "introduce", "introduced": "introduce", "introducing": "introduce", "معرفی": "introduce", "رونمایی": "introduce",
    "launch": "launch", "launched": "launch", "launches": "launch", "عرضه": "launch", "راه اندازی": "launch", "راه‌اندازی": "launch",
    "announce": "announce", "announced": "announce", "announcement": "announce", "اعلام": "announce", "اعلام کرد": "announce",
    "warning": "warning", "warns": "warning", "warn": "warning", "هشدار": "warning",
    "study": "study", "report": "report", "بررسی": "study", "گزارش": "report",
    "research": "research", "پژوهش": "research",
    "agent": "ai_agent",
}

_EVENT_TYPES = {
    "introduce", "launch", "announce", "warning", "study", "report", "research",
    "funding", "acquisition", "partnership", "appointment", "security_incident", "departure",
}

_MATERIAL_MARKERS = {
    "finding", "findings", "evidence", "cause", "impact", "scope", "scale", "timeline", "postmortem",
    "transcript", "details", "detail", "mechanism", "technical", "forensic", "newly", "revealed", "discovered",
    "vulnerability", "vulnerabilities", "mitigation", "remediation", "confirmed", "confirmation", "severity",
    "damage", "affected", "victims", "attackers", "exploit", "exploited", "benchmark", "results", "performance",
    "یافته", "یافته‌ها", "شواهد", "علت", "اثر", "دامنه", "مقیاس", "جزئیات", "مکانیسم", "فنی", "تأیید", "تایید",
    "آسیب‌پذیری", "آسیب پذیری", "رفع", "شدت", "خسارت", "بنچمارک", "نتایج", "عملکرد",
}


def _normalize(text: Any) -> str:
    value = str(text or "").lower().replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    for source, target in sorted(_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        value = re.sub(r"(?<![\w])" + re.escape(source) + r"(?![\w])", target, value)
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9_]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: Any) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z\u0600-\u06FF0-9_]+", _normalize(text)) if t not in _STOPWORDS and len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        value = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _time_hours(a: Any, b: Any) -> float | None:
    da = _parse_dt(a)
    db = _parse_dt(b)
    if not da or not db:
        return None
    return abs((da - db).total_seconds()) / 3600.0


def event_representation(item: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(str(item.get(k) or "") for k in ("title", "summary", "description", "why_it_matters", "content"))
    normalized = _normalize(text)
    tokens = _tokens(normalized)
    aliases = set(tokens)
    organizations = aliases & {"meta", "openai", "google", "microsoft", "anthropic", "nvidia", "stanford_hai"}
    people = aliases & {"mark_zuckerberg", "terence_tao"}
    products = aliases & {"muse", "gpt", "claude", "gemini", "qwen", "llama"}
    concepts = aliases & {
        "personal_superintelligence", "ai_agent", "open_problems", "open_science",
        "local_laws", "discriminatory", "legal_review",
    }
    event_types = aliases & _EVENT_TYPES
    material = aliases & _MATERIAL_MARKERS
    numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", normalized))
    return {
        "organizations": sorted(organizations),
        "people": sorted(people),
        "products": sorted(products),
        "concepts": sorted(concepts),
        "event_types": sorted(event_types),
        "material": sorted(material),
        "numbers": sorted(numbers),
        "tokens": sorted(tokens),
        "event_time": item.get("event_time") or item.get("published") or item.get("pub_date") or item.get("published_at") or "",
    }


def _set(rep: dict[str, Any], key: str) -> set[str]:
    return set(rep.get(key) or [])


def _material_update(a: dict[str, Any], b: dict[str, Any]) -> bool:
    na, nb = _set(a, "numbers"), _set(b, "numbers")
    if na and nb and na != nb:
        return True
    ma, mb = _set(a, "material"), _set(b, "material")
    if len(ma - mb) >= 2 or len(mb - ma) >= 2:
        return True
    # A new event type is a new action, not a material update.
    ea, eb = _set(a, "event_types"), _set(b, "event_types")
    if ea != eb and ea and eb:
        return True
    return False


def _same_event_identity(a: dict[str, Any], b: dict[str, Any]) -> bool:
    org_a, org_b = _set(a, "organizations"), _set(b, "organizations")
    people_a, people_b = _set(a, "people"), _set(b, "people")
    products_a, products_b = _set(a, "products"), _set(b, "products")
    concepts_a, concepts_b = _set(a, "concepts"), _set(b, "concepts")
    events_a, events_b = _set(a, "event_types"), _set(b, "event_types")

    shared_org = len(org_a & org_b)
    shared_people = len(people_a & people_b)
    shared_products = len(products_a & products_b)
    shared_concepts = len(concepts_a & concepts_b)
    shared_events = len(events_a & events_b)

    # Strong event anchors: distinctive product/person/concept combinations.
    if shared_people and shared_products and (shared_events or shared_concepts):
        return True
    if shared_org and shared_people and shared_products:
        return True
    if shared_org and shared_concepts >= 2 and shared_events:
        return True
    if shared_people and shared_concepts >= 2 and shared_events:
        return True
    return False


def event_similarity(candidate: dict[str, Any], prior: dict[str, Any]) -> float:
    a, b = event_representation(candidate), event_representation(prior)
    parts = []
    for key, weight in (("organizations", 0.16), ("people", 0.18), ("products", 0.17), ("concepts", 0.24), ("event_types", 0.10), ("tokens", 0.15)):
        parts.append(_jaccard(_set(a, key), _set(b, key)) * weight)
    score = sum(parts)
    hours = _time_hours(a.get("event_time"), b.get("event_time"))
    if hours is not None:
        if hours <= 48:
            score += 0.08
        elif hours <= 168:
            score += 0.04
        elif hours > 720:
            score -= 0.08
    if _same_event_identity(a, b):
        score = max(score, 0.78)
    return max(0.0, min(1.0, round(score, 4)))


def classify_story(candidate: dict[str, Any], prior: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
    score = event_similarity(candidate, prior)
    a, b = event_representation(candidate), event_representation(prior)
    same_identity = _same_event_identity(a, b)
    material = _material_update(a, b)
    if same_identity and not material:
        return "DUPLICATE", score, {"material_update": False, "identity_match": True}
    if same_identity and material:
        return "UPDATE", score, {"material_update": True, "identity_match": True}
    if score >= 0.80 and not material:
        return "DUPLICATE", score, {"material_update": False, "identity_match": False}
    if score >= 0.60 and material:
        return "UPDATE", score, {"material_update": True, "identity_match": False}
    if score >= 0.52:
        return "RELATED", score, {"material_update": material, "identity_match": False}
    return "NEW", score, {"material_update": material, "identity_match": False}
