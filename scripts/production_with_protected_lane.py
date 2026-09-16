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


def _is_mind_candidate(item: dict) -> bool:
    return bool(
        item.get("mind_lane_selected")
        or item.get("protected_editorial_lane") == "mind_ideas_voices"
        or item.get("lane") == "mind_ideas_voices"
    )


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
    mind = [item for item in candidates if _is_mind_candidate(item)][:SPECIAL_MAX_PER_PERIOD]
    non_mind = [item for item in candidates if not _is_mind_candidate(item)]
    bounded_normal = list(_ORIGINAL_BOUND(non_mind, max_posts=max_posts, policy=policy) or [])
    bounded = []
    seen = set()
    for item in bounded_normal + mind:
        marker = id(item)
        if marker in seen:
            continue
        seen.add(marker)
        bounded.append(item)
    print(
        f"[Dual Lane Budget Guard] normal_bounded={len(bounded) - len(mind)} mind={len(mind)} "
        f"output={len(bounded)} mind_quota={SPECIAL_MAX_PER_PERIOD} normal_score_floor=isolated",
        flush=True,
    )
    return bounded


def _final_score_dual(item):
    if _is_mind_candidate(item):
        try:
            return float(item.get("mind_editorial_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return _ORIGINAL_FINAL_SCORE(item)


def _protected_score_allowed_dual(score):
    # Mind has its own score domain and must never be tested against the normal
    # or legacy protected score floor.
    return True if _MIND_POLICY_ITEM.get("active") else _ORIGINAL_PROTECTED_SCORE_ALLOWED(score)


# The Mind lane must never masquerade as Tier-0. Keep the legacy helper intact
# for genuine protected leader/incident items only; publication policy receives
# Mind identity separately through runtime state below.
_MIND_POLICY_ITEM = {"active": False}

def _tier0_or_original(item):
    return _ORIGINAL_TIER0(item)


# Bind the canonical dual-lane functions into both module attributes and the
# already-created main() function global namespace. This avoids stale references
# captured by imported runtime modules.
_runtime_globals = production_entrypoint.main.__globals__
_runtime_globals["_bound_runtime_candidates"] = _dual_bound_runtime_candidates
_runtime_globals["_item_final_score"] = _final_score_dual
_runtime_globals["_is_tier0_publication_candidate"] = _tier0_or_original
_runtime_globals["protected_score_allowed"] = _protected_score_allowed_dual

production_entrypoint._bound_runtime_candidates = _dual_bound_runtime_candidates
production_entrypoint._item_final_score = _final_score_dual
production_entrypoint._is_tier0_publication_candidate = _tier0_or_original
production_entrypoint.protected_score_allowed = _protected_score_allowed_dual
period_ranked_pipeline.select_editorial = _select_dual_lane


# The policy function inside production_entrypoint.main is recreated on each run.
# Make its lane detector explicit by intercepting the current-item state through
# the final-score helper and protected-score guard. Mind score remains independent.
_original_entrypoint_main = production_entrypoint.main


def _patched_main(*, skip_education: bool = False):
    result = _original_entrypoint_main(skip_education=skip_education)
    return result


# Keep the public main callable unchanged while ensuring every global lookup
# resolves to the canonical dual-lane helpers above.
production_entrypoint.main.__globals__.update(
    {
        "_bound_runtime_candidates": _dual_bound_runtime_candidates,
        "_item_final_score": _final_score_dual,
        "_is_tier0_publication_candidate": _tier0_or_original,
        "protected_score_allowed": _protected_score_allowed_dual,
    }
)


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
