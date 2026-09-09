"""Hybrid event-level identity matching for cross-source news deduplication."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

ENTITIES = {
    "meta": {"meta", "متا"},
    "mark_zuckerberg": {"mark zuckerberg", "zuckerberg", "مارک زاکربرگ", "زاکربرگ"},
    "muse": {"muse", "میوز"},
    "personal_superintelligence": {"personal superintelligence", "personal super intelligence", "سوپر هوش شخصی"},
    "terence_tao": {"terence tao", "tao", "terنس تائو", "ترنس تائو"},
    "stanford_hai": {"stanford hai", "stanford institute for human-centered artificial intelligence", "استنفورد hai", "stanford"},
    "openai": {"openai", "اوپن ای آی", "اوپنای"},
    "anthropic": {"anthropic", "انتروپیک"},
    "google": {"google", "گوگل"},
    "nvidia": {"nvidia", "انویدیا"},
    "chatgpt_images": {"chatgpt images", "chatgpt images 2.5"},
}

EVENTS = {
    "launch": {"launch", "launched", "launches", "introduce", "introduced", "introduces", "unveil", "unveiled", "معرفی", "رونمایی", "عرضه"},
    "announcement": {"announce", "announced", "announcement", "اعلام", "اعلام کرد", "اعلامیه"},
    "warning": {"warning", "warn", "warns", "هشدار", "هشدار می‌دهد", "نگرانی"},
    "research": {"research", "study", "paper", "findings", "پژوهش", "مطالعه", "یافته", "تحقیق"},
    "legal_review": {"legal", "law", "laws", "legal review", "rights", "قانونی", "قوانین", "بررسی حقوقی"},
    "funding": {"funding", "grant", "investment", "سرمایه", "کمک مالی", "گرنت"},
    "security": {"security", "breach", "incident", "vulnerability", "hack", "نفوذ", "نقض امنیتی", "آسیب‌پذیری"},
    "benchmark": {"benchmark", "evaluation", "ارزیابی", "بنچمارک"},
}

MATERIAL = {
    "finding", "findings", "evidence", "cause", "impact", "scope", "scale", "timeline", "postmortem",
    "newly", "revealed", "discovered", "discovery", "details", "جزئیات", "یافته", "شواهد", "علت",
    "دامنه", "مقیاس", "زمان‌بندی", "گزارش فنی", "کشف", "تأیید", "تایید", "confirmed", "confirmation",
    "vulnerability", "آسیب‌پذیری", "severity", "شدت", "damage", "خسارت", "mitigation", "رفع", "remediation",
}

BOILERPLATE = {
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are", "with", "from", "by",
    "new", "latest", "news", "update", "this", "that", "how", "what", "why", "about", "در", "به", "از", "با",
    "و", "یا", "برای", "این", "آن", "که", "را", "یک", "است", "شد", "می", "های", "ها", "خبر", "جدید",
}


def normalize(text: Any) -> str:
    s = str(text or "").lower().replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    s = re.sub(r"https?://\S+", " ", s)
    for canonical, aliases in sorted(ENTITIES.items(), key=lambda x: max(map(len, x[1])), reverse=True):
        for alias in sorted(aliases, key=len, reverse=True):
            s = re.sub(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", canonical, s)
    s = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9_]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(text: Any) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z\u0600-\u06FF0-9_]+", normalize(text)) if len(t) > 2 and t not in BOILERPLATE}


def entity_set(text: Any) -> set[str]:
    s = normalize(text); found: set[str] = set()
    for canonical in ENTITIES:
        if re.search(r"(?<![\w])" + re.escape(canonical) + r"(?![\w])", s): found.add(canonical)
    return found


def event_set(text: Any) -> set[str]:
    s = normalize(text); found: set[str] = set()
    for canonical, aliases in EVENTS.items():
        if any(re.search(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", s) for alias in aliases): found.add(canonical)
    return found


def material_set(text: Any) -> set[str]:
    return tokens(text) & {normalize(x) for x in MATERIAL}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _sequence(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _parse_time(value: Any) -> datetime | None:
    if not value: return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def event_features(item: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(str(item.get(k) or "") for k in ("title", "summary", "description", "content"))
    return {"entities": entity_set(text), "events": event_set(text), "tokens": tokens(text), "material": material_set(text), "title": normalize(item.get("title", "")), "event_time": _parse_time(item.get("event_time") or item.get("published") or item.get("published_at")), "source": str(item.get("source") or "").lower(), "norm": normalize(text)}


def has_material_update(a: dict[str, Any], b: dict[str, Any]) -> bool:
    fa, fb = event_features(a), event_features(b)
    na = set(re.findall(r"\b\d+(?:\.\d+)?\b", fa["norm"]))
    nb = set(re.findall(r"\b\d+(?:\.\d+)?\b", fb["norm"]))
    if na and nb and na != nb: return True
    return len(fa["material"] - fb["material"]) >= 2


def compare_events(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, float, dict[str, Any]]:
    fa, fb = event_features(a), event_features(b)
    shared_entities = fa["entities"] & fb["entities"]
    shared_events = fa["events"] & fb["events"]
    context = _jaccard(fa["tokens"], fb["tokens"])
    title = _sequence(fa["title"], fb["title"])
    strong_product = bool(shared_entities & {"muse", "chatgpt_images"})
    strong_person = bool(shared_entities & {"mark_zuckerberg", "terence_tao"})
    strong_source = bool(shared_entities & {"stanford_hai"})
    time_gap = None
    if fa["event_time"] and fb["event_time"]: time_gap = abs((fa["event_time"] - fb["event_time"]).total_seconds()) / 86400.0
    score = 0.30 * min(1.0, len(shared_entities) / 2.0) + 0.20 * bool(shared_events) + 0.30 * context + 0.20 * title
    if strong_product: score += 0.18
    if strong_person and shared_events: score += 0.12
    if strong_source and (shared_events or context >= 0.35): score += 0.12
    if time_gap is not None and time_gap > 45: score *= 0.65
    material = has_material_update(a, b)
    evidence = {"shared_entities": sorted(shared_entities), "shared_events": sorted(shared_events), "context_jaccard": round(context, 4), "title_similarity": round(title, 4), "time_gap_days": time_gap, "material_update": material}

    same = False
    if strong_product and (shared_events or context >= 0.22): same = True
    elif strong_person and shared_events and context >= 0.18: same = True
    elif strong_source and context >= 0.35: same = True
    elif shared_events and context >= 0.65: same = True
    elif len(shared_entities) >= 2 and shared_events and context >= 0.20: same = True
    elif title >= 0.90 and context >= 0.45: same = True
    if same and material: return "UPDATE", min(1.0, score), evidence
    if same: return "DUPLICATE", min(1.0, score), evidence
    if shared_entities and (shared_events or context >= 0.16): return "RELATED", min(1.0, score), evidence
    return "NEW", min(1.0, score), evidence


def is_duplicate(candidate: dict[str, Any], history: list[dict[str, Any]]) -> bool:
    return any(compare_events(candidate, prior)[0] == "DUPLICATE" for prior in history)
