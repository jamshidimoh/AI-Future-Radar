"""Production launcher wrapper adding one bounded Mind/Ideas/Voices slot."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.protected_editorial_lane import choose_additive_candidate

# Importing the existing audited launcher installs all existing production hooks
# without changing their implementation.
import scripts.production_with_ranking_audit  # noqa: E402,F401
import production_entrypoint  # noqa: E402
import production_resilient_runner  # noqa: E402

_ORIGINAL_BOUND = production_entrypoint._bound_runtime_candidates
_ORIGINAL_SELECT = production_resilient_runner.production_entrypoint


def _protected_bound_runtime_candidates(candidates, max_posts: int, policy: dict):
    bounded = list(_ORIGINAL_BOUND(candidates, max_posts=max_posts, policy=policy) or [])
    if len(bounded) < 3:
        return bounded

    # Never alter the first three normal candidates. The extra slot is selected
    # only from the already-ranked replacement pool after those three items.
    main_three = bounded[:3]
    additive = choose_additive_candidate(
        bounded[3:],
        existing_ids={id(item) for item in main_three},
        max_rank=production_entrypoint.RANK_WINDOW,
    )
    if additive is None:
        print("[Mind/Ideas/Voices Lane] no qualifying additive candidate", flush=True)
        return bounded

    additive["protected_editorial_lane"] = "mind_ideas_voices"
    additive["protected_lane_reason"] = "ranked_replacement_candidate"
    print(
        "[Mind/Ideas/Voices Lane] additive candidate selected "
        f"rank={additive.get('normal_period_rank')} score={additive.get('final_editorial_score', additive.get('editorial_score'))} "
        f"type={additive.get('content_type')} mission={additive.get('mission_area')}",
        flush=True,
    )
    return main_three + [additive] + bounded[3:]


# The existing policy function counts all normal publications against the normal
# quota. Increase that quota only at production-runtime wrapper level so the
# fourth item can actually be published; selection still guarantees the first
# three are untouched and the fourth must be the protected-lane candidate.
production_entrypoint.MAX_NORMAL_NEWS_PER_PERIOD = max(
    3, int(os.getenv("RADAR_MIND_IDEAS_VOICES_TOTAL_CAP", "4") or 4)
)
production_entrypoint._bound_runtime_candidates = _protected_bound_runtime_candidates

if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
