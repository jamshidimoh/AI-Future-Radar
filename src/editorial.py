from editorial_clean import (
    classify_editorial_item as _classify_editorial_item,
    contract_summary,
    enrich_items as _enrich_items,
    filter_ai_relevance as _filter_ai_relevance,
    filter_low_signal,
)
from interview_evidence import has_interview_evidence
from unified_editorial_selection import load_editorial_contract, select_regular_portfolio


_AI_TAXONOMY_BRIDGE_TERMS = {
    "gpt", "chatgpt", "transformer", "neural network", "neural networks",
    "frontier model", "ai model", "autoresearch", "openai model", "anthropic model",
    "deepmind model", "claude model", "gemini model", "llama model", "qwen model",
    "mistral model", "openai", "anthropic", "deepmind", "chatgpt", "claude", "gemini",
    "llama", "qwen", "mistral", "هوش مصنوعی", "هوشِ مصنوعی", "یادگیری ماشین", "یادگیری عمیق",
    "مدل زبانی بزرگ", "مدل بنیادی", "هوش مصنوعی مولد", "هوش مولد", "عامل هوشمند",
    "عامل‌های هوشمند", "ایجنت هوشمند", "عامل‌های ai", "هوش عمومی مصنوعی", "مدل استدلالی",
    "بینایی ماشین", "ربات‌های هوشمند", "استفاده از رایانه", "ایمنی هوش مصنوعی",
    "حکمرانی هوش مصنوعی", "سیاست‌گذاری هوش مصنوعی", "آینده هوش مصنوعی", "آینده‌ی هوش مصنوعی",
    "داده مصنوعی", "شبکه عصبی", "شبکه‌های عصبی", "خودکارسازی پژوهش", "اتوماسیون پژوهش", "مدل مولد",
}

_RELEVANCE_STRONG_TERMS = {
    "artificial intelligence", "machine learning", "deep learning", "large language model", "llm",
    "foundation model", "generative ai", "agentic ai", "ai agent", "reasoning model", "multimodal",
    "computer vision", "ai coding", "llm inference", "llm training", "world model", "synthetic data",
    "ai safety", "ai alignment", "ai governance", "ai policy", "ai for science", "ai research",
    "ai benchmark", "physical ai", "embodied ai", "computer use", "هوش مصنوعی", "یادگیری ماشین",
    "یادگیری عمیق", "مدل زبانی بزرگ", "مدل بنیادی", "هوش مصنوعی مولد", "مدل استدلالی", "بینایی ماشین",
    "ایمنی هوش مصنوعی", "حکمرانی هوش مصنوعی", "سیاست‌گذاری هوش مصنوعی", "عامل هوشمند", "عامل‌های هوشمند",
}

_CURATED_DISCOVERY_CATEGORIES = {"ai", "quantum", "genetics", "mind", "future"}
_CURATED_CONTENT_TYPES = {
    "research", "paper", "study", "preprint", "official", "interview", "podcast", "talk",
    "lecture", "fireside", "conversation", "discussion", "q&a",
}
_TRUSTED_DISCOVERY_SOURCE_TYPES = {
    "youtube", "video", "podcast", "ai_lab", "research_lab", "university_lab", "university",
    "scientific_publisher", "science_media",
}


def _curated_discovery_context(item):
    category = str(item.get("category") or "").strip().lower()
    content_type = str(item.get("content_type") or "").strip().lower()
    source_type = str(item.get("source_type") or "").strip().lower()
    preferred_source = str(item.get("preferred_source") or "").strip()
    curated = bool(item.get("curated_discovery"))
    try:
        tier = int(item.get("source_tier"))
    except (TypeError, ValueError):
        tier = 3
    trusted = curated or bool(preferred_source) or source_type in _TRUSTED_DISCOVERY_SOURCE_TYPES
    if category not in _CURATED_DISCOVERY_CATEGORIES or tier not in {1, 2} or content_type not in _CURATED_CONTENT_TYPES or not trusted:
        return ""
    labels = {
        "ai": "AI",
        "quantum": "quantum AI",
        "genetics": "genetics AI",
        "mind": "mind and consciousness AI",
        "future": "future of AI and technology",
    }
    return f"Curated discovery policy category: {labels.get(category, category)}; source tier: {tier}; content type: {content_type}."


def _relevance_confidence(item):
    title = str(item.get("title") or "").lower()
    summary = str(item.get("summary") or "").lower()
    evidence = str(item.get("evidence_text") or "").lower()
    text = " ".join((title, summary, evidence))
    strong_hits = sum(1 for term in _RELEVANCE_STRONG_TERMS if term in text)
    bridge_hits = sum(1 for term in _AI_TAXONOMY_BRIDGE_TERMS if str(term).lower() in text)
    research_signal = bool(item.get("research_signal")) or any(
        term in text for term in ("research", "study", "experiment", "benchmark", "findings", "آزمایش", "پژوهش", "مطالعه")
    )
    source_tier = int(item.get("source_tier") or 3) if str(item.get("source_tier") or "").isdigit() else 3
    direct = strong_hits > 0 or bridge_hits >= 2
    confidence = 0.55
    if direct:
        confidence += 0.25
    if strong_hits >= 2:
        confidence += 0.10
    if research_signal:
        confidence += 0.05
    if source_tier == 1:
        confidence += 0.05
    elif source_tier >= 3:
        confidence -= 0.10
    if item.get("curated_discovery") and not direct:
        confidence -= 0.15
    return max(0.0, min(1.0, round(confidence, 3)))


def filter_ai_relevance(items, ai_keywords=None):
    """Apply the established AI relevance semantics and attach bounded confidence."""
    prepared = []
    context_used = 0
    for raw in items or []:
        item = dict(raw)
        evidence = str(item.get("evidence_text") or "").strip()
        context = _curated_discovery_context(item)
        if context:
            context_used += 1
            evidence = " ".join(part for part in (evidence, context) if part)
        if evidence:
            item["summary"] = " ".join(
                part for part in (str(item.get("summary") or "").strip(), evidence) if part
            )[:5000]
        prepared.append(item)
    effective_keywords = list(dict.fromkeys(list(ai_keywords or []) + sorted(_AI_TAXONOMY_BRIDGE_TERMS)))
    result = _filter_ai_relevance(prepared, effective_keywords)
    for item in result:
        item["ai_relevance_confidence"] = _relevance_confidence(item)
        item["ai_relevance_quality"] = (
            "high" if item["ai_relevance_confidence"] >= 0.90
            else "medium" if item["ai_relevance_confidence"] >= 0.75
            else "bridge"
        )
    result.sort(
        key=lambda x: (
            float(x.get("ai_relevance_confidence", 0)),
            float(x.get("priority_score", 0) or 0),
        ),
        reverse=True,
    )
    quality_counts = {"high": 0, "medium": 0, "bridge": 0}
    for item in result:
        quality_counts[item["ai_relevance_quality"]] += 1
    print(
        f"[AI Gate Context] curated_context={context_used} | input={len(prepared)} | output={len(result)}",
        flush=True,
    )
    print(
        f"[AI Gate Quality] high={quality_counts['high']} medium={quality_counts['medium']} bridge={quality_counts['bridge']}",
        flush=True,
    )
    return result


def classify_editorial_item(item, prior=None):
    result = dict(_classify_editorial_item(item, prior or {}))
    named = str(result.get("leader") or item.get("leader") or item.get("watch_person") or "").strip()
    if item.get("is_leader_watch") or item.get("leader_watch_protected"):
        result["leader"] = named
        result["leader_signal"] = True
        if named and has_interview_evidence({**item, **result}):
            result["interview_signal"] = True
            result["editorial_class"] = "leader_interview"
            result["editorial_confidence"] = 1.0
    return result


def enrich_items(items, leader_priorities, source_history=None, policy=None):
    enriched = _enrich_items(items, leader_priorities, source_history, policy)
    for item in enriched:
        if item.get("is_leader_watch") or item.get("leader_watch_protected"):
            item["leader_signal"] = True
            if item.get("leader") and has_interview_evidence(item):
                item["leader_watch_protected"] = True
    return enriched


def select_editorial(items, max_posts=4, max_per_source=2, max_per_type=2, policy=None):
    """Compatibility adapter; canonical selection lives in unified_editorial_selection."""
    policy = policy or {}
    contract = load_editorial_contract()
    return select_regular_portfolio(
        items,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        contract=contract,
        mission_aware=bool(policy.get("mission_aware", True)),
        strict_relevance=bool(policy.get("strict_relevance", False)),
    )


__all__ = [
    "classify_editorial_item",
    "contract_summary",
    "enrich_items",
    "filter_ai_relevance",
    "filter_low_signal",
    "select_editorial",
]
