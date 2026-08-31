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
    return result


def enrich_items(items, leader_priorities, source_history=None, policy=None):
    enriched = _enrich_items(items, leader_priorities, source_history, policy)
    for item in enriched:
        if item.get("is_leader_watch") or item.get("leader_watch_protected"):
            item["leader_signal"] = True
            if item.get("leader") and has_interview_evidence(item):
                item["leader_watch_protected"] = True
    return enriched


def filter_ai_relevance(items, ai_keywords=None):
    return _filter_ai_relevance(items, ai_keywords)


def _apply_strategic_signal(item):
    """Compatibility adapter to the canonical strategic signal scorer."""
    strategic = strategic_forecast_score(item)
    item["mission_score_base"] = round(float(item.get("mission_score", 0) or 0), 2)
    item["mission_score"] = round(float(item.get("mission_score", 0) or 0) + strategic, 2)
    return item


def select_editorial(items, max_posts=4, max_per_source=2, max_per_type=2, policy=None):
    """Legacy compatibility adapter; canonical portfolio selection is unified_editorial_selection."""
    policy = policy or {}
    return select_regular_portfolio(
        items,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        contract=load_editorial_contract(),
        mission_aware=bool(policy.get("mission_aware", True)),
        strict_relevance=bool(policy.get("strict_relevance", False)),
    )


__all__ = [
    "_apply_strategic_signal", "classify_editorial_item", "contract_summary", "enrich_items",
    "filter_ai_relevance", "filter_low_signal", "select_editorial",
]
