from editorial_clean import filter_ai_relevance as _filter_ai_relevance, enrich_items as _enrich_items, classify_editorial_item as _classify_editorial_item, contract_summary, filter_low_signal
from mission_selector import mission_score, select_mission_portfolio
from strategic_signal import strategic_forecast_score


def filter_ai_relevance(items, ai_keywords=None):
    """Apply the existing AI relevance semantics to all available source evidence."""
    prepared = []
    for raw in items or []:
        item = dict(raw)
        evidence = str(item.get("evidence_text") or "").strip()
        if evidence:
            item["summary"] = " ".join(
                part for part in (str(item.get("summary") or "").strip(), evidence) if part
            )[:5000]
        prepared.append(item)
    return _filter_ai_relevance(prepared, ai_keywords)


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
    if cap <= 0 or not items:
        return []
    scored = []
    for raw in items:
        x = dict(raw)
        mission_score(x)
        _apply_strategic_signal(x)
        scored.append(x)
    result = []
    used_sources = set()

    def source_key(x):
        return str(x.get("source") or x.get("source_domain") or "unknown").strip().casefold()

    def add_best(predicate, reason):
        candidates = [x for x in scored if source_key(x) not in used_sources and predicate(x)]
        if not candidates:
            return False
        chosen = max(candidates, key=lambda x: float(x.get("mission_score", 0) or 0))
        chosen["mission_selection_reason"] = reason
        result.append(chosen)
        used_sources.add(source_key(chosen))
        return True

    if len(result) < cap:
        add_best(lambda x: str(x.get("content_type") or "").lower() in {"research", "paper", "study", "preprint"} or x.get("research_signal"), "research_evidence")
    if len(result) < cap:
        add_best(lambda x: str(x.get("content_type") or "").lower() in {"news", "official", "product_news"} or x.get("news_signal"), "major_industry_news")

    remaining = [x for x in scored if source_key(x) not in used_sources]
    if len(result) < cap and remaining:
        extra = select_mission_portfolio(remaining, max_posts=cap - len(result), max_per_source=max_per_source, max_per_type=max_per_type)
        for x in extra:
            if source_key(x) in used_sources:
                continue
            if _leader_name(x) and (x.get("leader_watch_protected") or x.get("leader_signal") or x.get("leader_priority")):
                continue
            result.append(x)
            used_sources.add(source_key(x))
            if len(result) >= cap:
                break
    return result[:cap]


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
