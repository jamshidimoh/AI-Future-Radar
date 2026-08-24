"""Mission-aware final selection adapter for the production ranking path.

This module deliberately does not own AI relevance, publication policy, Telegram,
or protected Tier-0 leader routing. It only selects the normal candidate portfolio
from already-eligible stories using the existing mission scorer plus bounded
redundancy penalties.
"""
from __future__ import annotations

import time
from collections import Counter

from dedup import load_source_history
from mission_selector import _source_tier, classify_area, mission_score
from ranking_guard import filter_quality_candidates

_INTERVIEW_TYPES = {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a"}
_RESEARCH_TYPES = {"research", "paper", "study", "preprint"}


def _content_type(item: dict) -> str:
    return str(item.get("content_type") or "news").strip().lower()


def _source_key(item: dict) -> str:
    return str(item.get("source") or item.get("source_name") or "unknown").strip().casefold() or "unknown"


def _area(item: dict) -> str:
    value = str(item.get("mission_area") or "").strip()
    return value or classify_area(item)


def _is_interview(item: dict) -> bool:
    return _content_type(item) in _INTERVIEW_TYPES or bool(item.get("interview_signal"))


def _is_research(item: dict) -> bool:
    return _content_type(item) in _RESEARCH_TYPES or bool(item.get("research_signal"))


def _recent_source_counts(rotation_days: int) -> Counter:
    cutoff = time.time() - max(0, int(rotation_days)) * 86400
    counts: Counter = Counter()
    try:
        history = load_source_history()
    except Exception:
        history = []
    for record in history or []:
        try:
            ts = float(record.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff or str(record.get("content_type") or "").strip().lower() == "education":
            continue
        source = str(record.get("source") or "unknown").strip().casefold() or "unknown"
        counts[source] += 1
    return counts


def _quality_utility(item: dict, area_counts: Counter, type_counts: Counter, source_counts: Counter, recent_sources: Counter) -> tuple:
    base = float(item.get("final_editorial_score", 0) or item.get("editorial_score", 0) or 0)
    mission = float(item.get("mission_score", 0) or 0)
    signal = float(item.get("signal_score", 0) or 0)
    area = _area(item)
    ctype = _content_type(item)
    source = _source_key(item)

    # The existing canonical score remains primary. Mission score is only a
    # bounded tie-break/portfolio signal and cannot overwhelm a large editorial gap.
    utility = base + min(12.0, mission * 0.08) + min(4.0, signal * 0.04)

    # MMR-like redundancy control: repeated mission families/content types/sources
    # become less attractive, while no hard quota is imposed on any mission.
    utility -= min(10.0, area_counts[area] * 5.0)
    utility -= min(6.0, type_counts[ctype] * 3.0)
    utility -= min(5.0, source_counts[source] * 2.5)

    if _is_research(item) and type_counts[ctype] == 0:
        utility += 2.0
    if _is_interview(item) and type_counts[ctype] == 0:
        utility += 2.5
    if area not in area_counts:
        utility += 3.0

    # A non-AI mission family may enter the portfolio when it is genuinely close
    # to the leaders; this prevents the AI-heavy stream from starving quantum,
    # mind/cognition, future studies, or other convergence signals.
    if area != "ai_core" and not area_counts[area]:
        utility += 2.0

    # Preserve the existing seven-day source-rotation behavior as a soft penalty.
    utility -= min(8.0, recent_sources[source] * 3.0)

    tier = _source_tier(item)
    utility += {1: 2.0, 2: 0.5, 3: -2.0}.get(tier, -2.0)
    return (round(utility, 4), base, mission, signal)


def select_normal_portfolio(items: list[dict], max_posts: int, max_per_source: int, max_per_type: int, policy: dict | None = None) -> list[dict]:
    """Return a diverse normal portfolio without changing canonical score semantics."""
    policy = policy or {}
    rotation_days = int(policy.get("rotation_days", 7) or 7)
    recent_sources = _recent_source_counts(rotation_days)
    quality_candidates = filter_quality_candidates([dict(x) for x in (items or [])])
    prepared: list[dict] = []
    for item in quality_candidates:
        mission_score(item)
        item["mission_area"] = _area(item)
        item["source_rotation_count"] = int(recent_sources[_source_key(item)])
        prepared.append(item)

    prepared.sort(
        key=lambda x: (
            float(x.get("final_editorial_score", 0) or x.get("editorial_score", 0) or 0),
            float(x.get("mission_score", 0) or 0),
            float(x.get("signal_score", 0) or 0),
            str(x.get("published", "")),
        ),
        reverse=True,
    )

    selected: list[dict] = []
    area_counts: Counter = Counter()
    type_counts: Counter = Counter()
    source_counts: Counter = Counter()
    remaining = list(prepared)

    limit = max(0, int(max_posts or 0))
    source_cap = max(1, int(max_per_source or 1))
    type_cap = max(1, int(max_per_type or 1))

    while remaining and len(selected) < limit:
        eligible = [
            item for item in remaining
            if source_counts[_source_key(item)] < source_cap
            and type_counts[_content_type(item)] < type_cap
        ]
        if not eligible:
            break

        chosen = max(
            eligible,
            key=lambda item: _quality_utility(item, area_counts, type_counts, source_counts, recent_sources),
        )
        remaining.remove(chosen)
        source = _source_key(chosen)
        ctype = _content_type(chosen)
        area = _area(chosen)

        source_counts[source] += 1
        type_counts[ctype] += 1
        area_counts[area] += 1
        chosen["portfolio_rank"] = len(selected) + 1
        utility = _quality_utility(chosen, area_counts, type_counts, source_counts, recent_sources)[0]
        chosen["portfolio_selection_reason"] = (
            f"mission={area};utility={utility:.2f};source_tier={_source_tier(chosen)};"
            f"rotation_count={recent_sources[source]}"
        )
        chosen.setdefault("editorial_slot", "fallback")
        chosen.setdefault("selection_reason", "mission_aware_portfolio")
        selected.append(chosen)

    print(
        "[Mission-Aware Portfolio] "
        + " | ".join(
            f"rank={idx + 1}:area={item.get('mission_area')}:score={item.get('final_editorial_score', item.get('editorial_score', 0))}:"
            f"source={item.get('source')}:type={item.get('content_type')}"
            for idx, item in enumerate(selected)
        ),
        flush=True,
    )
    print(
        f"[Mission-Aware Portfolio] rotation_days={rotation_days} areas={dict(area_counts)} sources={dict(source_counts)} types={dict(type_counts)}",
        flush=True,
    )
    return selected
