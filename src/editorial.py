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

_AI_BRIDGE_TERMS = (
    "Claude", "GPT", "Gemini", "Qwen", "Llama", "DeepSeek", "Mistral",
    "OpenAI", "Anthropic", "transformer", "neural network", "reasoning model",
    "large language model", "artificial intelligence", "machine learning",
    "هوش مصنوعی", "هوشِ مصنوعی", "یادگیری ماشین", "یادگیری عمیق",
    "مدل زبانی بزرگ", "شبکه عصبی", "عامل هوشمند", "عامل‌های هوشمند",
)


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
    normalized = []
    for raw in items or []:
        item = dict(raw)
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        evidence = str(item.get("evidence_text") or "").strip()
        preferred = str(item.get("preferred_source") or "")
        combined = f"{title} {summary} {evidence}".casefold()
        bridge_hits = [term for term in _AI_BRIDGE_TERMS if term.casefold() in combined]
        curated_trusted = bool(item.get("curated_discovery") and preferred and int(item.get("source_tier") or 3) in {1, 2})

        # Quantum content is not automatically AI-relevant merely because its category is quantum.
        if str(item.get("category") or "").casefold() == "quantum" and not bridge_hits:
            item["_force_reject_ai_gate"] = True
        if evidence:
            item["description"] = " ".join(part for part in (item.get("description"), evidence) if part).strip()
        # Do not inject an artificial AI phrase into the text passed to the canonical gate.
        # Otherwise provenance-only items are incorrectly promoted from bridge to high quality.
        if bridge_hits:
            item["description"] = " ".join(part for part in (item.get("description"), "artificial intelligence") if part).strip()
        elif curated_trusted and not bridge_hits:
            item["description"] = " ".join(part for part in (item.get("description"), "curated AI provenance") if part).strip()
        item["_curated_trusted_ai_bridge"] = curated_trusted
        normalized.append(item)

    keywords = list(dict.fromkeys(list(ai_keywords or []) + list(_AI_BRIDGE_TERMS)))
    result = _filter_ai_relevance([x for x in normalized if not x.get("_force_reject_ai_gate")], keywords)

    trusted_curated = [
        x for x in normalized
        if x.get("_curated_trusted_ai_bridge") and not x.get("_force_reject_ai_gate") and not any(
            term.casefold() in f"{x.get('title','')} {x.get('summary','')} {x.get('evidence_text','')}".casefold()
            for term in _AI_BRIDGE_TERMS
        )
    ]
    present = {str(x.get("title") or "") for x in result}
    for item in trusted_curated:
        if str(item.get("title") or "") in present:
            continue
        accepted = dict(item)
        accepted.update(
            _ai_link=True,
            relevance_reason="curated_ai_provenance",
            topic_family="ai_core",
            relevance_evidence=["curated AI provenance"],
            evidence_level="B",
            ai_relevance_confidence=0.55,
            evidence_strength=5.5,
            ai_relevance_quality="bridge",
        )
        result.append(accepted)

    for item in result:
        if item.get("relevance_reason") == "curated_ai_provenance":
            item["ai_relevance_quality"] = "bridge"
            continue
        evidence = str(item.get("evidence_text") or "").strip()
        confidence = 0.95 if evidence else 0.85
        item["ai_relevance_confidence"] = confidence
        item["evidence_strength"] = max(float(item.get("evidence_strength", 0) or 0), confidence * 10.0)
        item["ai_relevance_quality"] = "high" if confidence >= 0.90 else "medium"
    return result


def _apply_strategic_signal(item):
    strategic = strategic_forecast_score(item)
    item["mission_score_base"] = round(float(item.get("mission_score", 0) or 0), 2)
    item["mission_score"] = round(float(item.get("mission_score", 0) or 0) + strategic, 2)
    return item


def _is_protected_leader(item):
    return bool(item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("leader_signal"))


def _leader_name(item):
    return str(item.get("leader") or item.get("watch_person") or "").strip()


def select_editorial(items, max_posts=4, max_per_source=2, max_per_type=2, policy=None):
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
        interviewed = has_interview_evidence(item)
        item["editorial_slot"] = "leader_interview" if interviewed else "fallback"
        item["editorial_class"] = "leader_interview" if interviewed else item.get("editorial_class", "leader_activity")
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
