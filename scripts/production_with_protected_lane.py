"""Production launcher adding a score-driven Mind/Ideas/Voices lane."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import production_entrypoint  # noqa: E402
import production_resilient_runner  # noqa: E402
import scripts.production_with_ranking_audit  # noqa: E402,F401
from src.protected_editorial_lane import choose_additive_candidates  # noqa: E402

# Reuse the existing audited production launcher and all existing contracts.
_ORIGINAL_BOUND = production_entrypoint._bound_runtime_candidates
_ORIGINAL_TIER0 = production_entrypoint._is_tier0_publication_candidate
SPECIAL_MAX_PER_PERIOD = 2


def _protected_bound_runtime_candidates(candidates, max_posts: int, policy: dict):
    bounded = list(_ORIGINAL_BOUND(candidates, max_posts=max_posts, policy=policy) or [])
    if len(bounded) < 3:
        return bounded

    # Keep the canonical first three normal candidates untouched. Add at most two
    # qualifying candidates from the already-bounded ranked replacement pool.
    main_three = bounded[:3]
    specials = choose_additive_candidates(
        bounded[3:],
        existing_ids={id(item) for item in main_three},
        max_rank=production_entrypoint.RANK_WINDOW,
        max_items=SPECIAL_MAX_PER_PERIOD,
    )
    for item in specials:
        item["protected_editorial_lane"] = "mind_ideas_voices"
        item["protected_slot"] = True
        item["protected_content"] = True
        item["protected_lane_reason"] = "score_driven_additive_mind_ideas_voices"

    if not specials:
        print("[Mind/Ideas/Voices Lane] no qualifying additive candidates", flush=True)
        return main_three

    print(
        f"[Mind/Ideas/Voices Lane] score_driven_additive={len(specials)} count_cap={SPECIAL_MAX_PER_PERIOD}",
        flush=True,
    )
    for item in specials:
        print(
            "[Mind/Ideas/Voices Lane] candidate "
            f"rank={item.get('normal_period_rank')} score={item.get('final_editorial_score', item.get('editorial_score'))} "
            f"type={item.get('content_type')} mission={item.get('mission_area')} source={item.get('source')}",
            flush=True,
        )
    return main_three + specials


# Special-lane items use the existing protected publication route only for quota
# isolation; their eligibility is still the normal score floor, and no separate
# protected-score bypass is introduced.
def _tier0_or_special(item):
    return _ORIGINAL_TIER0(item) or item.get("protected_editorial_lane") == "mind_ideas_voices"


production_entrypoint._bound_runtime_candidates = _protected_bound_runtime_candidates
production_entrypoint._is_tier0_publication_candidate = _tier0_or_special

if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
