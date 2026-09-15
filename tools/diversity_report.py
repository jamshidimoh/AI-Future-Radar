"""Diagnostic: report real published-content diversity from data/seen.json.

The mission-lane system in config/mission_policy.yaml (ai_core_target_min,
convergence_target, mind_cognition_target, ...) and the rotation window
(config/mission_policy.yaml: rotation) are both best-effort — a target only
fills if a qualifying candidate actually clears the AI-relevance and evidence
gates in that run, and the rotation cap is bypassed as a last resort rather
than blocking publication. Neither mechanism is directly observable from the
persisted state, so this script is the only way to check, after the fact,
whether the feed is actually diversifying in production rather than just in
the config file.

Usage:
    python tools/diversity_report.py [--window N]

--window N restricts the report to the last N published (non-education)
history entries; defaults to all available history.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.unified_editorial_selection import mission_area  # noqa: E402

SEEN_PATH = ROOT / "data" / "seen.json"


def _load_history() -> list[dict]:
    try:
        payload = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {SEEN_PATH}: {exc}", file=sys.stderr)
        return []
    history = payload.get("source_history", [])
    return [r for r in history if str(r.get("content_type") or "").strip().lower() != "education"]


def _report(history: list[dict]) -> None:
    total = len(history)
    if not total:
        print("No non-education publication history available.")
        return
    categories = Counter(str(r.get("category") or "unknown") for r in history)
    sources = Counter(str(r.get("source") or "unknown") for r in history)
    content_types = Counter(str(r.get("content_type") or "unknown") for r in history)
    # mission_area falls back to the legacy `category` field (see _AREA_MAP in
    # unified_editorial_selection.py) for older entries that predate the
    # mission_area persistence fix, so this is meaningful across the full history.
    areas = Counter(mission_area(r) for r in history)

    print(f"Publication diversity report — {total} published items\n")

    print("Mission area distribution (mission_area, with legacy-category fallback):")
    for area, count in areas.most_common():
        print(f"  {area:<20} {count:>4}  ({count / total:.1%})")

    print("\nLegacy category distribution (as persisted, LLM-assigned):")
    for cat, count in categories.most_common():
        print(f"  {cat:<20} {count:>4}  ({count / total:.1%})")

    print("\nContent type distribution:")
    for ctype, count in content_types.most_common():
        print(f"  {ctype:<20} {count:>4}  ({count / total:.1%})")

    print(f"\nTop sources (of {len(sources)} unique):")
    for source, count in sources.most_common(10):
        print(f"  {source:<35} {count:>4}  ({count / total:.1%})")

    top_source, top_count = sources.most_common(1)[0]
    if top_count / total >= 0.25:
        print(
            f"\n⚠ '{top_source}' accounts for {top_count / total:.0%} of published items "
            f"in this window — check window_source_counts in the [Source Diversity Gate] "
            f"run logs to confirm the rotation cap is actually engaging."
        )
    if areas.most_common(1)[0][1] / total >= 0.9:
        print(
            "⚠ One mission area accounts for 90%+ of published items — the "
            "guaranteed lane slots (ai_core_target_min / convergence_target / "
            "mind_cognition_target) are likely going unfilled for lack of "
            "qualifying candidates most runs, not by policy design."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=None, help="Limit to the last N non-education history entries.")
    args = parser.parse_args()
    history = _load_history()
    if args.window:
        history = history[-args.window:]
    _report(history)


if __name__ == "__main__":
    main()
