from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .priority_people import is_substantive_priority_interview

MAX_NORMAL_NEWS_PER_PERIOD = 3
MAX_EXTRA_NEWS = 2
RANK_WINDOW = 4


def _score(item: Dict[str, Any]) -> float:
    for key in ("final_editorial_score", "leader_story_score", "mission_score", "editorial_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
            if value:
                return value
        except (TypeError, ValueError):
            pass
    return 0.0


def _eligible(item: Dict[str, Any]) -> bool:
    return not item.get("duplicate") and not item.get("publication_blocked") and item.get("quality_gate", True) is not False


def rank_period_candidates(items: Iterable[Dict[str, Any]], normal_window: int = RANK_WINDOW) -> List[Dict[str, Any]]:
    """Return global ranking with independent normal-news ranks."""
    eligible = [dict(x) for x in items if _eligible(x)]
    eligible.sort(key=lambda x: (_score(x), str(x.get("published", ""))), reverse=True)
    tier0 = [x for x in eligible if is_substantive_priority_interview(x)]
    normal = [x for x in eligible if not is_substantive_priority_interview(x)][:max(0, int(normal_window))]
    ranked = tier0 + normal
    normal_rank = 0
    tier0_rank = 0
    for global_rank, item in enumerate(ranked, 1):
        item["period_rank"] = global_rank
        item["final_editorial_score"] = _score(item)
        if is_substantive_priority_interview(item):
            tier0_rank += 1
            item["tier0_rank"] = tier0_rank
            item["normal_period_rank"] = None
        else:
            normal_rank += 1
            item["normal_period_rank"] = normal_rank
            item["tier0_rank"] = None
    return ranked


def select_news_for_period(items: Iterable[Dict[str, Any]], previous_published_score: Optional[float]) -> List[Dict[str, Any]]:
    """Select only the normal-news stream using the 1+2 policy."""
    ranked = rank_period_candidates(items, normal_window=RANK_WINDOW)
    normal = [x for x in ranked if x.get("normal_period_rank") is not None]
    if not normal:
        return []
    primary = normal[0]
    selected = [primary]
    if previous_published_score is None:
        return selected
    baseline = float(previous_published_score)
    extras = [x for x in normal[1:RANK_WINDOW] if _score(x) > baseline]
    selected.extend(extras[:MAX_EXTRA_NEWS])
    return selected[:MAX_NORMAL_NEWS_PER_PERIOD]
