"""Canonical publication-value score.

Editorial scoring answers whether an item is suitable for publication in the
Radar. Technology-signal features remain outside this score and are owned by
``signal_engine``.
"""
from __future__ import annotations

import re
from typing import Any

WEIGHTS = {"mission_fit": 0.30, "source_authority": 0.20, "evidence_confidence": 0.20, "publication_value": 0.15, "freshness": 0.15}

_PRODUCT_RELEASE_ACTIONS = (
    "launch", "launches", "launched", "announce", "announces", "release", "releases", "released", "unveil", "unveils",
    "unveiled", "introduce", "introduces", "introduced", "now available",
    "general availability", "public preview", "announced", "debut", "ships",
    "معرفی کرد", "عرضه شد", "منتشر شد", "در دسترس قرار گرفت",
)
_AI_PRODUCT_EVIDENCE = (
    "artificial intelligence", " ai ", "agi", "machine learning", "deepmind",
    "openai", "anthropic", "nvidia", "foundation model", "world model",
    "genie", "simulator", "simulation", "reasoning model", "multimodal",
    "ai agent", "agentic", "robotics", "model", "product", "platform",
    "شبیه‌ساز", "شبیه ساز", "مدل بنیادی", "مدل هوش مصنوعی", "هوش مصنوعی",
)
_PRODUCT_SHAPE = (
    "world model", "simulator", "simulation", "interactive world", "foundation model",
    "reasoning model", "multimodal model", "ai agent", "agentic", "robotics model",
    "model", "product", "platform", "capability", "assistant", "system",
    "شبیه‌ساز", "شبیه ساز", "محصول", "مدل", "قابلیت", "سامانه", "پلتفرم",
)
_STRATEGIC_INFRASTRUCTURE = (
    "electricity", "power demand", "power supply", "power grid", "energy infrastructure",
    "data center power", "data centre power", "data center", "datacenter", "compute capacity",
    "compute bottleneck", "compute infrastructure", "chips", "semiconductor", "inference cost",
    "energy", "electricity", "grid", "capacity constraint", "infrastructure", "workforce",
    "jobs", "economy", "regulation", "governance", "ai safety", "competition",
    "برق", "انرژی", "شبکه برق", "زیرساخت محاسباتی", "تراشه", "مرکز داده",
)
_AI_CONTEXT = (
    "artificial intelligence", " ai ", "agi", "machine learning", "deepmind", "openai",
    "anthropic", "nvidia", "gpt", "claude", "gemini", "world model", "ai agent",
    "هوش مصنوعی", "یادگیری ماشین",
)
_LEADER_NAMES = (
    "elon musk", "sam altman", "demis hassabis", "jensen huang", "andrew ng",
    "eric schmidt", "dario amodei", "bill gates", "mustafa suleyman", "yann lecun",
    "geoffrey hinton", "yuval noah harari", "stuart russell", "ilya sutskever",
    "ایلان ماسک", "سم آلتمن", "دمیس هسابیس", "جنسن هوانگ", "اندرو انگ",
    "اریک اشمیت", "داریو آمودی", "بیل گیتس", "مصطفی سلیمان", "یان لکون",
    "جفری هینتون", "یووال نوح هراری", "استوارت راسل", "ایلیا سوتسکیور",
)
_ATTRIBUTION_TERMS = (
    "says", "said", "warns", "warned", "argues", "argued", "predicts", "predicted",
    "believes", "believe", "claims", "claimed", "notes", "noted", "according to",
    "calls for", "points out", "writes", "wrote", "said that", "warned that",
    "می‌گوید", "هشدار داد", "معتقد است", "پیش‌بینی کرد", "اظهار کرد",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = f" {text.casefold()} "
    return any(term.casefold() in normalized for term in terms)


def is_major_ai_product_release(item: dict[str, Any]) -> bool:
    """Recognize consequential AI product/capability launches beyond LLM version bumps."""
    text = " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "description", "source", "model_name", "tags")
    ).casefold()
    if not _contains_any(text, _PRODUCT_RELEASE_ACTIONS):
        return False
    ai_context = bool(
        item.get("_ai_link") or item.get("ai_relevant") or item.get("ai_relevance")
        or _contains_any(text, _AI_PRODUCT_EVIDENCE)
    )
    product_shape = _contains_any(text, _PRODUCT_SHAPE)
    content_type = str(item.get("content_type") or "").strip().casefold()
    official_ai_org = _contains_any(text, (
        "google deepmind", "deepmind", "openai", "anthropic", "nvidia", "microsoft ai",
        "meta ai", "xai", "mistral", "hugging face", "amazon aws",
    ))
    return bool(ai_context and product_shape and (
        content_type in {"product_news", "official", "news", "research", "leader_signal"}
        or official_ai_org
    ))


def is_strategic_leader_statement(item: dict[str, Any]) -> bool:
    """Recognize attributed, consequential technology statements by monitored leaders."""
    text = " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "description", "source", "watch_person", "leader")
    ).casefold()
    leader = bool(
        str(item.get("watch_person") or item.get("leader") or "").strip()
        or _contains_any(text, _LEADER_NAMES)
    )
    strategic_topic = _contains_any(text, _STRATEGIC_INFRASTRUCTURE)
    ai_context = _contains_any(text, _AI_CONTEXT)
    content_type = str(item.get("content_type") or "").strip().casefold()
    attributed_headline = bool(re.search(r"\b(?:elon musk|sam altman|demis hassabis|jensen huang|andrew ng|eric schmidt)\s*[:—-]", text))
    attribution = _contains_any(text, _ATTRIBUTION_TERMS) or attributed_headline or content_type in {
        "leader_signal", "direct_statement", "social_post", "statement", "opinion",
    }
    return bool(leader and strategic_topic and ai_context and attribution)


def _clip(value: Any) -> float:
    try:
        numeric = 0.0 if value is None else value
        return max(0.0, min(1.0, float(numeric)))
    except (TypeError, ValueError):
        return 0.0


def build_features(item: dict[str, Any]) -> dict[str, float]:
    try:
        tier_value = item.get("source_tier", item.get("tier", 3))
        tier = int(tier_value or 3)
    except (TypeError, ValueError):
        tier = 3
    source_authority = {1: 1.0, 2: 0.75, 3: 0.45}.get(tier, 0.30)
    try:
        raw_age = item.get("freshness_hours")
        age = float(raw_age) if raw_age is not None else None
    except (TypeError, ValueError):
        age = None
    freshness = 0.40 if age is None else 1.0 if age <= 24 else 0.90 if age <= 48 else 0.80 if age <= 72 else 0.60 if age <= 168 else 0.30 if age <= 720 else 0.10
    ctype = str(item.get("content_type") or "").strip().lower()
    cls = str(item.get("editorial_class") or "").strip().lower()
    # Product/capability launches and strategic statements are distinct news
    # classes, not just generic "company news" or low-weight social content.
    if is_major_ai_product_release(item): publication_value = 1.0
    elif is_strategic_leader_statement(item): publication_value = 0.95
    elif cls in {"research_breakthrough", "leader_interview"}: publication_value = 1.0
    elif ctype in {"research", "paper", "study", "interview", "podcast", "lecture", "talk", "conversation"}: publication_value = 0.90
    elif cls in {"major_industry_news", "convergence_signal", "ai_signal"}: publication_value = 0.80
    elif ctype in {"news", "official", "product_news"}: publication_value = 0.70
    else: publication_value = 0.45
    try: evidence_strength = _clip(float(item.get("evidence_strength", 0) or 0) / 10.0)
    except (TypeError, ValueError): evidence_strength = 0.0
    evidence_confidence = max(evidence_strength, 1.0 if str(item.get("evidence_text") or "").strip() else 0.0, 1.0 if item.get("research_signal") else 0.0)
    mission_fit = 1.0 if any(item.get(k) for k in ("_ai_link", "ai_relevant", "mission_area")) else 0.0
    return {"mission_fit": mission_fit, "source_authority": source_authority, "evidence_confidence": evidence_confidence, "publication_value": publication_value, "freshness": freshness}


def score_editorial_v2(item: dict[str, Any]) -> tuple[float, dict[str, float]]:
    features = build_features(item)
    return round(sum(features[k] * WEIGHTS[k] for k in WEIGHTS) * 100.0, 2), features
