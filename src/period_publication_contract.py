from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.priority_people import is_substantive_priority_interview

MAX_NORMAL_NEWS_PER_PERIOD = 8  # anti-flood ceiling, not expected publication volume
MAX_EXTRA_NEWS = MAX_NORMAL_NEWS_PER_PERIOD - 1
RANK_WINDOW = 12
NORMAL_SCORE_FLOOR = 55.0
NORMAL_RELATIVE_SCORE_GAP = 15.0


def _score(item: dict[str, Any]) -> float:
    for key in ("final_editorial_score", "leader_story_score", "mission_score", "editorial_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
            if value:
                return value
        except (TypeError, ValueError):
            pass
    return 0.0


def _eligible(item: dict[str, Any]) -> bool:
    return not item.get("duplicate") and not item.get("publication_blocked") and item.get("quality_gate", True) is not False


def rank_period_candidates(items: Iterable[dict[str, Any]], normal_window: int = RANK_WINDOW) -> list[dict[str, Any]]:
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


def select_news_for_period(items: Iterable[dict[str, Any]], previous_published_score: float | None = None) -> list[dict[str, Any]]:
    """Select every qualifying distinct story up to the safety ceiling.

    The previous published score remains an accepted argument for compatibility,
    but it is not an eligibility gate for newly discovered news.
    """
    ranked = rank_period_candidates(items, normal_window=RANK_WINDOW)
    normal = [x for x in ranked if x.get("normal_period_rank") is not None]
    if not normal:
        return []
    best_score = max(_score(item) for item in normal)
    threshold = max(NORMAL_SCORE_FLOOR, best_score - NORMAL_RELATIVE_SCORE_GAP)
    qualified = [item for item in normal if _score(item) >= threshold]
    return qualified[:MAX_NORMAL_NEWS_PER_PERIOD]
