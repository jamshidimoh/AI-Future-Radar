from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_unified_selection() -> None:
    path = ROOT / "src" / "unified_editorial_selection.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("def mission_area(")
    end = text.index("\ndef _mission_text", start)
    replacement = '''def mission_area(item: dict[str, Any]) -> str:
    explicit = str(item.get("mission_area") or "").strip().casefold()
    if explicit in _AREA_MAP.values() or explicit in {"unclassified", "unknown"}:
        return explicit
    category = str(item.get("category") or "").strip().casefold()
    if category in _AREA_MAP:
        return _AREA_MAP[category]
    matched_area = _keyword_match_area(item)
    if matched_area:
        return matched_area
    if item.get("_ai_link") is True or item.get("ai_relevance") is True:
        return "ai_core"
    return "unclassified"
'''
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")


def patch_pipeline() -> None:
    path = ROOT / "period_ranked_pipeline.py"
    text = path.read_text(encoding="utf-8")
    old = '''def canonical_rank_score(item):
    editorial = _base_editorial_score(item)
    signal = float(item.get("signal_score", 0) or 0)
    return round(editorial * EDITORIAL_WEIGHT + signal * SIGNAL_WEIGHT, 2)
'''
    new = '''def canonical_rank_score(item):
    editorial = _base_editorial_score(item)
    signal = float(item.get("signal_score", 0) or 0)
    base_score = round(editorial * EDITORIAL_WEIGHT + signal * SIGNAL_WEIGHT, 2)
    try:
        coverage_bonus = max(0.0, min(1.5, float(item.get("mission_coverage_bonus", 0) or 0)))
    except (TypeError, ValueError):
        coverage_bonus = 0.0
    return round(base_score + coverage_bonus, 2)
'''
    if old not in text:
        raise SystemExit("patch target not found: canonical_rank_score")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_main() -> None:
    path = ROOT / "main.py"
    text = path.read_text(encoding="utf-8")
    marker = 'def _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes):'
    start = text.index(marker)
    match = re.search(r"\n^def \w+\(", text[start + len(marker):], flags=re.MULTILINE)
    end = start + len(marker) + (match.start() if match else len(text) - (start + len(marker)))
    block = text[start:end]
    old = '    contract = load_editorial_contract()\n'
    new = '''    contract = load_editorial_contract()
    from src.dedup import load_source_history
    from src.mission_coverage_priority import annotate_recovery_candidates

    try:
        source_history = load_source_history()
    except Exception as exc:
        logger.warning("Mission coverage history unavailable: %s", exc, exc_info=True)
        source_history = []
    editorial_pool = annotate_recovery_candidates(editorial_pool, source_history, contract)
'''
    if old not in block:
        raise SystemExit("patch target not found: mission recovery contract")
    block = block.replace(old, new, 1)
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def add_helper() -> None:
    path = ROOT / "src" / "mission_coverage_priority.py"
    content = '''"""Deterministic historical mission-lane priority for recovery candidates."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.unified_editorial_selection import mission_area

_TARGET_KEYS = {
    "ai_core": "ai_core_target_min",
    "convergence": "convergence_target",
    "mind_cognition": "mind_cognition_target",
    "future_governance": "mind_future_target",
}


def _score(item: dict[str, Any]) -> float:
    for key in ("final_editorial_score", "radar_composite_score", "editorial_score", "mission_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value:
            return value
    return 0.0


def _tier(item: dict[str, Any]) -> int | None:
    try:
        value = item.get("source_tier", item.get("tier"))
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def historical_area_counts(history: Iterable[dict[str, Any]], window_items: int) -> dict[str, int]:
    recent = [x for x in history or [] if str(x.get("content_type") or "").strip().casefold() != "education"]
    recent = recent[-max(0, int(window_items or 0)):] if window_items else []
    counts: dict[str, int] = {}
    for record in recent:
        area = mission_area(record)
        counts[area] = counts.get(area, 0) + 1
    return counts


def mission_coverage_bonus(item: dict[str, Any], area_counts: dict[str, int], contract: dict[str, Any]) -> float:
    area = mission_area(item)
    target_key = _TARGET_KEYS.get(area)
    if not target_key or int(contract.get(target_key, 0) or 0) <= 0:
        return 0.0
    count = int(area_counts.get(area, 0) or 0)
    if count >= 2:
        return 0.0
    if _score(item) < 52.0:
        return 0.0
    if _tier(item) not in {1, 2}:
        return 0.0
    return 1.5 if count == 0 else 0.75


def annotate_recovery_candidates(items: Iterable[dict[str, Any]], history: Iterable[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    window_items = int(contract.get("window_runs", 6) or 6) * max(1, int(contract.get("max_posts", 3) or 3))
    counts = historical_area_counts(history, window_items)
    prepared: list[dict[str, Any]] = []
    for raw in items or []:
        item = dict(raw)
        item["historical_mission_area_count"] = int(counts.get(mission_area(item), 0) or 0)
        item["mission_coverage_bonus"] = mission_coverage_bonus(item, counts, contract)
        prepared.append(item)
    prepared.sort(key=lambda x: (float(x.get("mission_coverage_bonus", 0) or 0), _score(x), str(x.get("published", ""))), reverse=True)
    return prepared
'''
    if path.exists():
        raise SystemExit(f"helper already exists: {path}")
    path.write_text(content, encoding="utf-8")


def add_tests() -> None:
    path = ROOT / "tests" / "test_mission_coverage_priority.py"
    content = '''from src.mission_coverage_priority import annotate_recovery_candidates, historical_area_counts, mission_coverage_bonus
from src.unified_editorial_selection import mission_area
from period_ranked_pipeline import canonical_rank_score


def test_mission_area_uses_keyword_classification_before_research_fallback():
    item = {"title": "Could there ever be a viable test for artificial consciousness?", "category": "research", "content_type": "research"}
    assert mission_area(item) == "mind_cognition"


def test_mission_area_does_not_default_unclassified_to_ai_core():
    item = {"title": "Observations on an unrelated historical dataset", "category": "", "content_type": "news"}
    assert mission_area(item) == "unclassified"


def test_historical_area_counts_ignore_education_and_use_recent_window():
    history = [
        {"content_type": "education", "mission_area": "mind_cognition"},
        {"content_type": "news", "mission_area": "ai_core"},
        {"content_type": "news", "mission_area": "mind_cognition"},
    ]
    assert historical_area_counts(history, 2) == {"ai_core": 1, "mind_cognition": 1}


def test_underrepresented_authoritative_mind_candidate_gets_bounded_bonus():
    contract = {"window_runs": 6, "max_posts": 3, "mind_cognition_target": 1}
    item = {"mission_area": "mind_cognition", "final_editorial_score": 54.15, "source_tier": 1}
    assert mission_coverage_bonus(item, {"ai_core": 53, "mind_cognition": 1}, contract) == 0.75
    annotated = annotate_recovery_candidates([item], [], contract)[0]
    assert annotated["mission_coverage_bonus"] == 1.5
    assert annotated["historical_mission_area_count"] == 0


def test_coverage_bonus_is_bounded_and_additive():
    item = {"radar_composite_score": 54.15, "signal_score": 0, "mission_coverage_bonus": 0.75}
    assert canonical_rank_score(item) == 41.36
'''
    if path.exists():
        raise SystemExit(f"test file already exists: {path}")
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    patch_unified_selection()
    patch_pipeline()
    patch_main()
    add_helper()
    add_tests()
    print("mission coverage patch applied")
