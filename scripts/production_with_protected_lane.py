"""Production launcher with an independent Mind/Ideas/Voices publication lane."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import production_entrypoint  # noqa: E402
import production_resilient_runner  # noqa: E402
import period_ranked_pipeline  # noqa: E402
import scripts.production_with_ranking_audit  # noqa: E402,F401
from src.protected_editorial_lane import (  # noqa: E402
    SPECIAL_MAX_PER_PERIOD,
    choose_additive_candidates,
)

# Keep the existing audited normal-news selector intact, but build the second
# domain from the full discovery set instead of from the normal candidate window.
_ORIGINAL_SELECT_EDITORIAL = period_ranked_pipeline.select_editorial
_ORIGINAL_BOUND = production_entrypoint._bound_runtime_candidates
_ORIGINAL_TIER0 = production_entrypoint._is_tier0_publication_candidate
_ORIGINAL_FINAL_SCORE = production_entrypoint._item_final_score
_ORIGINAL_PROTECTED_SCORE_ALLOWED = production_entrypoint.protected_score_allowed

_MIND_CONTEXT = {"active": False}


def _select_dual_lane(items, max_posts, max_per_source, max_per_type, policy):
    normal_candidates = list(
        _ORIGINAL_SELECT_EDITORIAL(items, max_posts, max_per_source, max_per_type, policy) or []
    )
    normal_ids = {id(item) for item in normal_candidates}
    mind_candidates = choose_additive_candidates(
        items,
        existing_ids=normal_ids,
        max_items=SPECIAL_MAX_PER_PERIOD,
    )
    for item in mind_candidates:
        print(
            "[Mind/Ideas/Voices Selection] "
            f"rank={item.get('mind_period_rank')} score={item.get('mind_editorial_score')} "
            f"normal_score={item.get('editorial_score', 0)} title={str(item.get('title', ''))[:120]}",
            flush=True,
        )
    print(
        f"[Dual Lane Selection] normal={len(normal_candidates)} mind_ideas_voices={len(mind_candidates)} "
        f"mind_cap={SPECIAL_MAX_PER_PERIOD} mind_score_floor=not_applied",
        flush=True,
    )
    return normal_candidates + mind_candidates


def _dual_bound_runtime_candidates(candidates, max_posts: int, policy: dict):
    candidates = list(candidates or [])
    mind = [item for item in candidates if item.get("mind_lane_selected")]
    non_mind = [item for item in candidates if not item.get("mind_lane_selected")]
    bounded = list(_ORIGINAL_BOUND(non_mind, max_posts=max_posts, policy=policy) or [])
    seen = {id(item) for item in bounded}
    for item in mind:
        if id(item) not in seen and len(mind) <= SPECIAL_MAX_PER_PERIOD:
            bounded.append(item)
            seen.add(id(item))
    print(
        f"[Dual Lane Budget Guard] normal_bounded={len(bounded) - len(mind)} mind={len(mind)} "
        f"output={len(bounded)} mind_quota={SPECIAL_MAX_PER_PERIOD} normal_score_floor=isolated",
        flush=True,
    )
    return bounded


def _tier0_or_mind(item):
    is_mind = bool(item.get("mind_lane_selected")) or item.get("protected_editorial_lane") == "mind_ideas_voices"
    _MIND_CONTEXT["active"] = is_mind
    if is_mind:
        return True
    return _ORIGINAL_TIER0(item)


def _final_score_dual(item):
    if item.get("mind_lane_selected") or item.get("protected_editorial_lane") == "mind_ideas_voices":
        try:
            return float(item.get("mind_editorial_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return _ORIGINAL_FINAL_SCORE(item)


def _protected_score_allowed_dual(score):
    # The special lane has already passed its own eligibility gate and its own
    # independent score. It must never be tested against PROTECTED_SCORE_FLOOR.
    if _MIND_CONTEXT.get("active"):
        return True
    return _ORIGINAL_PROTECTED_SCORE_ALLOWED(score)


period_ranked_pipeline.select_editorial = _select_dual_lane
production_entrypoint._bound_runtime_candidates = _dual_bound_runtime_candidates
production_entrypoint._is_tier0_publication_candidate = _tier0_or_mind
production_entrypoint._item_final_score = _final_score_dual
production_entrypoint.protected_score_allowed = _protected_score_allowed_dual


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
