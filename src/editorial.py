from editorial_clean import (
    classify_editorial_item as _classify_editorial_item,
    contract_summary,
    enrich_items as _enrich_items,
    filter_ai_relevance as _filter_ai_relevance,
    filter_low_signal,
)
from interview_evidence import has_interview_evidence
from strategic_signal import strategic_forecast_score
from future_significance import annotate_future_significance
from unified_editorial_selection import load_editorial_contract, select_regular_portfolio

_AI_BRIDGE_TERMS = (
    "Claude", "GPT", "Gemini", "Qwen", "Llama", "DeepSeek", "Mistral",
    "OpenAI", "Anthropic", "transformer", "neural network", "reasoning model",
    "large language model", "artificial intelligence", "machine learning",
    "هوش مصنوعی", "هوشِ مصنوعی", "یادگیری ماشین", "یادگیری عمیق",
    "مدل زبانی بزرگ", "شبکه عصبی", "عامل هوشمند", "عامل‌های هوشمند",
)

_EARLY_STRATEGIC_TERMS = (
    "ai governance", "ai policy", "ai regulation", "artificial intelligence regulation",
    "technology policy", "digital policy", "frontier model", "ai safety", "ai security",
    "ai agents", "agentic ai", "ai infrastructure", "ai chip", "ai data center",
    "هوش مصنوعی", "حکمرانی هوش مصنوعی", "سیاست‌گذاری هوش مصنوعی", "تنظیم‌گری هوش مصنوعی",
)
_CONSEQUENTIAL_TERMS = (
    "breach", "hack", "hacked", "security incident", "safety incident", "rogue agent",
    "misuse", "shutdown", "recall", "regulatory action", "critical vulnerability",
    "data leak", "agent hijack",
)
_EMERGING_TERMS = (
    "quantum computing", "quantum computer", "quantum chip", "qubit", "brain-computer interface",
    "bci", "neurotechnology", "humanoid robot", "physical ai", "robot foundation model",
    "ai accelerator", "gpu", "npu", "tpu", "photonic computing", "neuromorphic",
    "synthetic biology", "protein design", "computational biology",
)


def _contains_any(text, terms):
    return any(str(term).casefold() in text for term in terms)


def _early_inclusion_reason(item, combined):
    leader = bool(item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("is_leader"))
    interview = has_interview_evidence(item)
    if leader and interview:
        return "leader_interview"
    if leader and str(item.get("leader") or item.get("watch_person") or "").strip():
        return "key_actor"
    # Strategic signals take precedence over generic consequence language such as
    # "regulator" when an item is explicitly about AI/technology policy.
    if _contains_any(combined, _EARLY_STRATEGIC_TERMS) and (_contains_any(combined, _AI_BRIDGE_TERMS) or str(item.get("category") or "").casefold() in {"ai", "future"}):
        return "strategic_ai_or_tech"
    if _contains_any(combined, _CONSEQUENTIAL_TERMS) and _contains_any(combined, _AI_BRIDGE_TERMS + _EARLY_STRATEGIC_TERMS):
        return "consequential_ai_or_tech"
    if _contains_any(combined, _EMERGING_TERMS):
        try:
            tier = int(item.get("source_tier") or 3)
        except (TypeError, ValueError):
            tier = 3
        if tier in {1, 2} or item.get("curated_discovery"):
            return "emerging_technology"
    return ""


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
    rescue = []
    supplied_keywords = tuple(str(term) for term in (ai_keywords or ()) if str(term).strip())
    for raw in items or []:
        item = dict(raw)
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        evidence = str(item.get("evidence_text") or "").strip()
        preferred = str(item.get("preferred_source") or "")
        combined = f"{title} {summary} {evidence}".casefold()
        bridge_hits = [term for term in _AI_BRIDGE_TERMS if term.casefold() in combined]
        direct_keyword_hits = [term for term in supplied_keywords if term.casefold() in combined]
        curated_trusted = bool(item.get("curated_discovery") and preferred and int(item.get("source_tier") or 3) in {1, 2})
        early_reason = _early_inclusion_reason(item, combined)

        if str(item.get("category") or "").casefold() == "quantum" and not bridge_hits and not direct_keyword_hits and not early_reason:
            item["_force_reject_ai_gate"] = True
        if evidence:
            item["description"] = " ".join(part for part in (item.get("description"), evidence) if part).strip()
        if bridge_hits:
            item["description"] = " ".join(part for part in (item.get("description"), "artificial intelligence") if part).strip()
        item["_curated_trusted_ai_bridge"] = curated_trusted
        item["_has_direct_ai_evidence"] = bool(bridge_hits or direct_keyword_hits)

        # Existing AI evidence remains on the normal relevance path for generic
        # interviews; this preserves the established ai_evidence contract. For
        # substantive strategic/news signals, early inclusion can still annotate
        # the item even when "AI" appears as a generic keyword.
        generic_interview_with_ai_evidence = bool(
            str(item.get("content_type") or "").casefold() == "interview"
            and not (item.get("is_leader_watch") or item.get("leader_watch_protected"))
            and direct_keyword_hits
        )
        if early_reason and not bridge_hits and not generic_interview_with_ai_evidence:
            item["early_inclusion"] = True
            item["early_inclusion_reason"] = early_reason
            item["relevance_reason"] = f"early_inclusion:{early_reason}"
            item["_ai_link"] = True
            item["ai_relevance"] = True
            item["ai_relevance_confidence"] = 0.55 if early_reason in {"key_actor", "emerging_technology"} else 0.65
            item["evidence_strength"] = max(float(item.get("evidence_strength", 0) or 0), 5.5)
            item["ai_relevance_quality"] = "early_inclusion"
            rescue.append(item)
        else:
            normalized.append(item)

    keywords = list(dict.fromkeys(list(ai_keywords or []) + list(_AI_BRIDGE_TERMS)))
    result = _filter_ai_relevance(
        [
            x for x in normalized
            if not x.get("_force_reject_ai_gate")
            and (not x.get("_curated_trusted_ai_bridge") or x.get("_has_direct_ai_evidence"))
        ],
        keywords,
    )

    trusted_curated = [
        x for x in normalized
        if x.get("_curated_trusted_ai_bridge")
        and not x.get("_force_reject_ai_gate")
        and not x.get("_has_direct_ai_evidence")
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

    result.extend(rescue)
    for item in result:
        if item.get("relevance_reason") == "curated_ai_provenance" or item.get("early_inclusion"):
            continue
        evidence = str(item.get("evidence_text") or "").strip()
        confidence = 0.95 if evidence else 0.85
        item["ai_relevance_confidence"] = confidence
        item["evidence_strength"] = max(float(item.get("evidence_strength", 0) or 0), confidence * 10.0)
        item["ai_relevance_quality"] = "high" if confidence >= 0.90 else "medium"
    print(f"[Early Inclusion] rescued={len(rescue)} | direct/curated={len(result) - len(rescue)}", flush=True)
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


def _annotate_selection_value(item):
    """Add future-significance value without changing any hard quality gate."""
    annotate_future_significance(item)
    item["final_editorial_score"] = item["radar_composite_score"]
    return item


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
    for item in regular:
        _annotate_selection_value(item)
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
