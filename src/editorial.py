from editorial_clean import filter_ai_relevance, enrich_items as _enrich_items, classify_editorial_item as _classify_editorial_item, contract_summary, filter_low_signal
from mission_selector import mission_score, select_mission_portfolio, _source_tier
from strategic_signal import strategic_forecast_score


def classify_editorial_item(item, prior=None):
    result = dict(_classify_editorial_item(item, prior or {}))
    named = str(result.get("leader") or item.get("leader") or item.get("watch_person") or "").strip()
    if item.get("is_leader_watch") or item.get("leader_watch_protected"):
        result["leader"] = named
        result["leader_signal"] = True
        ctype = str(item.get("content_type") or "").lower()
        if named and (result.get("interview_signal") or ctype in {"interview", "podcast", "talk", "conversation", "fireside", "discussion", "q&a"}):
            result["interview_signal"] = True
            result["editorial_class"] = "leader_interview"
            result["editorial_confidence"] = 1.0
    return result


def enrich_items(items, leader_priorities, source_history=None, policy=None):
    enriched = _enrich_items(items, leader_priorities, source_history, policy)
    for item in enriched:
        if item.get("is_leader_watch") or item.get("leader_watch_protected"):
            item["leader_signal"] = True
            if item.get("leader") and item.get("interview_signal"):
                item["leader_watch_protected"] = True
    return enriched


def _leader_name(item):
    return str(item.get("leader") or item.get("watch_person") or "").strip()


def _is_named_leader_interview(item, allow_explicit_leader=False):
    """Recognize protected named-leader interviews without weakening fallback semantics."""
    name = _leader_name(item)
    if not name:
        return False
    ctype = str(item.get("content_type") or "").lower()
    is_interview = bool(item.get("interview_signal")) or ctype in {"interview", "podcast", "talk", "conversation", "fireside", "discussion", "q&a"}
    if not is_interview:
        return False
    return bool(
        item.get("is_leader_watch")
        or item.get("leader_watch_protected")
        or str(item.get("editorial_slot") or "").casefold() == "leader_interview"
        or (allow_explicit_leader and item.get("leader"))
    )


def _is_protected_leader_activity(item):
    """Keep named leader activity in the protected stream; never let it re-enter regular portfolio selection."""
    name = _leader_name(item)
    if not name:
        return False
    flag = bool(
        item.get("is_leader_watch")
        or item.get("leader_watch_protected")
        or item.get("leader_signal")
        or item.get("leader_priority")
    )
    if not flag:
        return False
    ctype = str(item.get("content_type") or "").lower()
    return bool(
        item.get("leader_activity_signal")
        or ctype in {"product_news", "official"}
    ) and not _is_named_leader_interview(item, allow_explicit_leader=True)


def _mark_leader_slot(item):
    out = dict(item)
    out["editorial_slot"] = "leader_interview"
    out["editorial_class"] = "leader_interview"
    out["leader_watch_protected"] = True
    out["leader_signal"] = True
    out["leader_interview"] = True
    out["selection_reason"] = f"protected:leader_interview:{_leader_name(out)}"
    return out


def _apply_strategic_signal(item):
    """Boost high-impact forecasts and strategic-risk stories independently of watchlist membership."""
    strategic = strategic_forecast_score(item)
    item["mission_score_base"] = round(float(item.get("mission_score", 0) or 0), 2)
    item["mission_score"] = round(float(item.get("mission_score", 0) or 0) + strategic, 2)
    return item


def _regular_portfolio(items, cap, max_per_source, max_per_type):
    """Select the regular stream only through the canonical mission portfolio.

    The previous implementation had separate research/news fast paths that could
    bypass source-authority and analytical-anchor safeguards enforced by
    ``select_mission_portfolio``. That made low-authority aggregators and community
    items able to occupy normal slots despite the central editorial policy.
    """
    if cap <= 0 or not items:
        return []

    scored = []
    for raw in items:
        x = dict(raw)
        mission_score(x)
        _apply_strategic_signal(x)
        scored.append(x)

    authoritative = [
        x for x in scored
        if int(x.get("source_tier_effective", _source_tier(x)) or 3) <= 2
        and bool(x.get("analytical_anchor"))
    ]

    if not authoritative:
        return []

    selected = select_mission_portfolio(
        authoritative,
        max_posts=cap,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
    )
    for item in selected:
        item.setdefault("mission_selection_reason", "mission_portfolio")
    return selected[:cap]


def select_editorial(items, max_posts=4, max_per_source=2, max_per_type=2, policy=None):
    """Mission portfolio while preserving hard leader, research, news, and strategic-forecast contracts."""
    policy = policy or {}
    protected_limit = int(policy.get("protected_slots", policy.get("leader_interview_slots", policy.get("leader_protected_max", 2))) or 2)
    allow_explicit_leader = protected_limit > 0
    protected = []
    regular = []
    seen_people = set()
    for raw in items or []:
        item = dict(raw)
        if _is_named_leader_interview(item, allow_explicit_leader=allow_explicit_leader) or _is_protected_leader_activity(item):
            person = _leader_name(item).casefold()
            if person in seen_people:
                continue
            seen_people.add(person)
            protected.append(item)
        else:
            regular.append(item)

    protected.sort(key=lambda x: (
        int(x.get("leader_priority", 0) or 0),
        float(x.get("editorial_score", 0) or 0),
        float(x.get("signal_score", 0) or 0),
        str(x.get("published", "")),
    ), reverse=True)
    selected_protected = [_mark_leader_slot(x) for x in protected[:protected_limit]]

    regular_cap = max(0, int(max_posts))
    regular_selected = _regular_portfolio(regular, regular_cap, max_per_source, max_per_type)

    selected = selected_protected + regular_selected
    for item in selected:
        if item.get("is_leader_watch") and not _leader_name(item):
            item["editorial_slot"] = "fallback"
            item["selection_reason"] = "leader_watch_without_named_guest"
            item["leader_signal"] = True
    return selected
