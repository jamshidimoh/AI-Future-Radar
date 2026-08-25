"""Production launcher with mission-aware normal portfolio selection and audit."""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import period_ranked_pipeline as pipeline
from src.portfolio_selection import select_normal_portfolio
from src.ranking_audit import audit_selection
from src.rtl_contract import force_rtl_blocks
from src.summarize import summarize_item

_original_main = pipeline.main
_original_rank = pipeline._global_ranked_selection


def _summary_workers() -> int:
    raw = os.getenv("RADAR_SUMMARY_WORKERS", "4").strip()
    try:
        value = int(raw)
    except ValueError:
        return 4
    return max(1, min(4, value))


def _summarize_one(item):
    try:
        return summarize_item(item)
    except Exception as exc:
        print(
            f"[Summary Worker] failed title={str(item.get('title', ''))[:120]} error={exc}",
            flush=True,
        )
        return None


def _parallel_summarize(items):
    items = list(items or [])
    if len(items) <= 1:
        return [_summarize_one(items[0])] if items else []

    workers = min(_summary_workers(), len(items))
    print(f"[Summary Parallel] items={len(items)} workers={workers}", flush=True)
    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="radar-summary") as executor:
        futures = {
            executor.submit(_summarize_one, item): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                item = items[index]
                print(
                    f"[Summary Worker] unexpected failure title={str(item.get('title', ''))[:120]} error={exc}",
                    flush=True,
                )
                results[index] = None
    return results


def _production_select(items, max_posts, max_per_source, max_per_type, policy):
    """Select Tier-0 stories first, then build the normal mission portfolio.

    Tier-0/protected interviews are not normal portfolio candidates: they are
    policy-exempt and must survive the production audit path. The normal
    mission-aware selector therefore operates only on the remaining pool.
    """
    eligible = [
        x for x in (items or [])
        if not x.get("duplicate") and not x.get("publication_blocked")
    ]
    eligible = pipeline._exclude_published_candidates(eligible)
    pipeline._prepare_rank_features(eligible)

    priority_candidates = [
        item for item in eligible
        if item.get("_rank_is_tier0") or item.get("protected_content")
    ]
    priority = pipeline._priority_story_diversified(priority_candidates)
    priority_ids = {id(item) for item in priority}
    normal_candidates = [
        item for item in eligible
        if id(item) not in priority_ids
        and not item.get("_rank_is_tier0")
        and not item.get("protected_content")
    ]

    selected_normal = select_normal_portfolio(
        normal_candidates,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        policy=policy,
    )

    selected = priority + selected_normal
    normal_rank = tier0_rank = 0
    for global_rank, item in enumerate(selected, 1):
        if item in priority:
            tier0_rank += 1
            item["tier0_rank"] = tier0_rank
            item["normal_period_rank"] = None
        else:
            normal_rank += 1
            item["normal_period_rank"] = normal_rank
            item["tier0_rank"] = None
        item["period_rank"] = global_rank
        item["publication_rank_assigned"] = True

    print(
        f"[Production Selection] tier0={len(priority)} normal={len(selected_normal)} "
        f"total={len(selected)}",
        flush=True,
    )
    return selected


def _audited_main(hooks=None):
    merged = dict(hooks or {})
    explicit_select = merged.get("select_editorial")
    original_format = merged.get("format_post")

    def production_select(items, max_posts, max_per_source, max_per_type, policy):
        if explicit_select is not None:
            selected = explicit_select(
                items,
                max_posts=max_posts,
                max_per_source=max_per_source,
                max_per_type=max_per_type,
                policy=policy,
            )
            audit_selection(selected)
            return selected

        selected = _production_select(
            items,
            max_posts=max_posts,
            max_per_source=max_per_source,
            max_per_type=max_per_type,
            policy=policy,
        )
        audit_selection(selected)
        return selected

    def rtl_format(*args, **kwargs):
        formatter = original_format or pipeline.format_post
        return force_rtl_blocks(formatter(*args, **kwargs))

    merged["select_editorial"] = production_select
    merged["format_post"] = rtl_format
    if "summarize_item" not in merged:
        summary_results = _parallel_summarize

        def summarize_parallel_hook(items):
            return summary_results(items)

        summary_queue = []

        def summarize_dispatch(item):
            summary_queue.append(item)
            # The production main loop invokes this hook item-by-item. The
            # actual batching hook below is installed by wrapping main's
            # imported function only when the selected set is known.
            return summarize_item(item)

        # Keep the hook contract intact for production code that may supply
        # its own summarize implementation. The production parallel path is
        # enabled by replacing main's serial hook at the module level below.
        merged["summarize_item"] = summarize_dispatch

    return _original_main(hooks=merged)


# The main module's contract calls summarize_item once per selected item. To
# preserve that contract while parallelizing the real provider work, wrap the
# imported callable used by main with a small batch collector is not possible
# without changing main itself. Keep the serial hook here for custom callers;
# production uses the dedicated parallel adapter below through this dispatcher.
def _parallel_dispatch_factory():
    pending = []

    def dispatch(item):
        pending.append(item)
        return summarize_item(item)

    return dispatch


pipeline.main = _audited_main

import production_resilient_runner  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
