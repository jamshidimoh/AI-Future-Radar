from editorial_clean import (
    classify_editorial_item as _classify_editorial_item,
    contract_summary,
    enrich_items as _enrich_items,
    filter_ai_relevance as _filter_ai_relevance,
    filter_low_signal,
)
from interview_evidence import has_interview_evidence
from strategic_signal import strategic_forecast_score
from unified_editorial_selection import load_editorial_contract, select_regular_portfolio


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
        elif not named:
            result["editorial_class"] = "fallback"
            result["editorial_confidence"] = 0.35
    return result


def enrich_items(items, leader_priorities, source_history=None, policy=None):
    enriched = _enrich_items(items, leader_priorities, source_history, policy)
    for item in enriched:
        if item.get("is_leader_watch") or item.get("leader_watch_protected"):
            item["leader_signal"] = True
            if item.get("leader") and has_interview_evidence(item):
                item["leader_watch_protected"] = True
            elif not item.get("leader"):
                item["editorial_slot"] = "fallback"
                item["editorial_class"] = "fallback"
    return enriched


def filter_ai_relevance(items, ai_keywords=None):
    bridge_keywords = [
        "Claude", "GPT", "Gemini", "Qwen", "Llama", "DeepSeek", "Mistral",
        "OpenAI", "Anthropic", "transformer", "neural network", "reasoning model",
        "large language model", "artificial intelligence", "machine learning",
        "هوش مصنوعی", "یادگیری ماشین", "مدل زبانی بزرگ", "شبکه عصبی", "عامل هوشمند",
    ]
    normalized = []
    for raw in items or []:
        item = dict(raw)
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        evidence = str(item.get("evidence_text") or "").strip()
        source = str(item.get("source") or "")
        preferred = str(item.get("preferred_source") or "")
        bridge_parts = []
        bridge_confidence = 0.0
        direct_evidence = False
        if evidence:
            bridge_parts.append(evidence)
            direct_evidence = True
            bridge_confidence = 0.95
        combined = f"{title} {summary} {evidence}".casefold()
        if any(term.casefold() in combined for term in bridge_keywords):
            direct_evidence = True
            bridge_confidence = max(bridge_confidence, 0.85)
        if item.get("curated_discovery") and preferred:
            bridge_parts.append("curated AI provenance")
            bridge_confidence = max(bridge_confidence, 0.55)
        if bridge_parts:
            item["description"] = " ".join(bridge_parts)
        if any(term.casefold() in combined for term in ("Claude", "GPT", "Gemini", "Qwen", "Llama", "DeepSeek", "Mistral", "OpenAI", "Anthropic", "transformer", "neural network", "reasoning model", "large language model")):
            item["description"] = "artificial intelligence " + str(item.get("description") or "")
        elif any(term in combined for term in ("هوش مصنوعی", "یادگیری ماشین", "مدل زبانی بزرگ", "شبکه عصبی", "عامل هوشمند")):
            item["description"] = "artificial intelligence " + str(item.get("description") or "")
        normalized.append(item)

    keywords = list(ai_keywords or []) + bridge_keywords
    result = _filter_ai_relevance(normalized, keywords)
    for item in result:
        evidence = str(item.get("evidence_text") or "").strip()
        curated = bool(item.get("curated_discovery"))
        confidence = 0.55 if curated and not evidence else (0.95 if evidence else 0.85)
        item["ai_relevance_confidence"] = confidence
        item["evidence_strength"] = max(float(item.get("evidence_strength", 0) or 0), confidence * 10.0)
        item["relevance_reason"] = "ai_evidence" if evidence or confidence >= 0.85 else item.get("relevance_reason", "ai_evidence")
    return result


def _apply_strategic_signal(item):
    """Compatibility adapter to the canonical strategic signal scorer."""
    strategic = strategic_forecast_score(item)
    item["mission_score_base"] = round(float(item.get("mission_score", 0) or 0), 2)
    item["mission_score"] = round(float(item.get("mission_score", 0) or 0) + strategic, 2)
    return item


def _is_protected_leader(item):
    return bool(item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("leader_signal"))


def _leader_name(item):
    return str(item.get("leader") or item.get("watch_person") or "").strip()


def select_editorial(items, max_posts=4, max_per_source=2, max_per_type=2, policy=None):
    """Deprecated compatibility adapter; production selection remains canonical."""
    policy = policy or {}
    protected_limit = int(policy.get("protected_slots", policy.get("leader_interview_slots", 2)) or 0)
    protected, regular = [], []
    seen = set()
    for raw in items or []:
        item = dict(raw)
        name = _leader_name(item).casefold()
        if _is_protected_leader(item) and name:
            if name in seen:
                continue
            seen.add(name)
            protected.append(item)
        else:
            regular.append(item)
    protected.sort(key=lambda x: (int(x.get("leader_priority", 0) or 0), float(x.get("editorial_score", 0) or 0), str(x.get("published", ""))), reverse=True)
    protected = protected[:protected_limit]
    for item in protected:
        item["editorial_slot"] = "leader_interview" if has_interview_evidence(item) else "fallback"
        item["editorial_class"] = "leader_interview" if has_interview_evidence(item) else item.get("editorial_class", "leader_activity")
        item["leader_watch_protected"] = True
        item["leader_signal"] = True
        item["selection_reason"] = f"protected:{_leader_name(item)}"
    selected_regular = select_regular_portfolio(
        regular,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        contract=load_editorial_contract(),
        mission_aware=bool(policy.get("mission_aware", True)),
        strict_relevance=bool(policy.get("strict_relevance", False)),
    )
    for item in selected_regular:
        if item.get("is_leader_watch") and not _leader_name(item):
            item["editorial_slot"] = "fallback"
            item["editorial_class"] = "fallback"
    return protected + selected_regular


__all__ = [
    "_apply_strategic_signal", "classify_editorial_item", "contract_summary", "enrich_items",
    "filter_ai_relevance", "filter_low_signal", "select_editorial",
]
