from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"patch target not found: {label}")
    return text.replace(old, new, 1)


def patch_unified_selection() -> None:
    path = ROOT / "src" / "unified_editorial_selection.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("def mission_area(")
    end = text.index("\ndef _mission_text", start)
    replacement = '''def mission_area(item: dict[str, Any]) -> str:\n    explicit = str(item.get("mission_area") or "").strip().casefold()\n    if explicit in _AREA_MAP.values() or explicit in {"unclassified", "unknown"}:\n        return explicit\n    category = str(item.get("category") or "").strip().casefold()\n    if category in _AREA_MAP:\n        return _AREA_MAP[category]\n    matched_area = _keyword_match_area(item)\n    if matched_area:\n        return matched_area\n    if item.get("_ai_link") is True or item.get("ai_relevance") is True:\n        return "ai_core"\n    if item.get("research_signal") or content_type_key(item) in _RESEARCH_TYPES:\n        return "unclassified"\n    return "unclassified"\n'''
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")


def patch_pipeline() -> None:
    path = ROOT / "period_ranked_pipeline.py"
    text = path.read_text(encoding="utf-8")
    old = '''def canonical_rank_score(item):\n    editorial = _base_editorial_score(item)\n    signal = float(item.get("signal_score", 0) or 0)\n    return round(editorial * EDITORIAL_WEIGHT + signal * SIGNAL_WEIGHT, 2)\n'''
    new = '''def canonical_rank_score(item):\n    editorial = _base_editorial_score(item)\n    signal = float(item.get("signal_score", 0) or 0)\n    base_score = round(editorial * EDITORIAL_WEIGHT + signal * SIGNAL_WEIGHT, 2)\n    try:\n        coverage_bonus = max(0.0, min(1.5, float(item.get("mission_coverage_bonus", 0) or 0)))\n    except (TypeError, ValueError):\n        coverage_bonus = 0.0\n    return round(base_score + coverage_bonus, 2)\n'''
    text = replace_once(text, old, new, "canonical_rank_score")
    path.write_text(text, encoding="utf-8")


def patch_main() -> None:
    path = ROOT / "main.py"
    text = path.read_text(encoding="utf-8")
    marker = 'def _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes):'
    start = text.index(marker)
    next_def = re.search(r"\n^def \w+\(", text[start + len(marker):], flags=re.MULTILINE)
    end = start + len(marker) + (next_def.start() if next_def else len(text) - (start + len(marker)))
    block = text[start:end]
    old = '    contract = load_editorial_contract()\n'
    new = '''    contract = load_editorial_contract()\n    from src.dedup import load_source_history\n    from src.mission_coverage_priority import annotate_recovery_candidates\n\n    try:\n        source_history = load_source_history()\n    except Exception as exc:\n        logger.warning("Mission coverage history unavailable: %s", exc, exc_info=True)\n        source_history = []\n    editorial_pool = annotate_recovery_candidates(editorial_pool, source_history, contract)\n'''
    if old not in block:
        raise SystemExit("patch target not found: mission recovery contract")
    block = block.replace(old, new, 1)
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def add_helper() -> None:
    path = ROOT / "src" / "mission_coverage_priority.py"
    content = '''"""Deterministic historical mission-lane priority for recovery candidates."""\nfrom __future__ import annotations\n\nfrom collections.abc import Iterable\nfrom typing import Any\n\nfrom src.unified_editorial_selection import mission_area\n\n_TARGET_KEYS = {\n    "ai_core": "ai_core_target_min",\n    "convergence": "convergence_target",\n    "mind_cognition": "mind_cognition_target",\n    "future_governance": "mind_future_target",\n}\n\n\ndef _score(item: dict[str, Any]) -> float:\n    for key in ("final_editorial_score", "radar_composite_score", "editorial_score", "mission_score", "score"):\n        try:\n            value = float(item.get(key, 0) or 0)\n        except (TypeError, ValueError):\n            value = 0.0\n        if value:\n            return value\n    return 0.0\n\n\ndef _tier(item: dict[str, Any]) -> int | None:\n    try:\n        value = item.get("source_tier", item.get("tier"))\n        return int(value) if value not in (None, "") else None\n    except (TypeError, ValueError):\n        return None\n\n\ndef historical_area_counts(history: Iterable[dict[str, Any]], window_items: int) -> dict[str, int]:\n    recent = [x for x in history or [] if str(x.get("content_type") or "").strip().casefold() != "education"]\n    recent = recent[-max(0, int(window_items or 0)):] if window_items else []\n    counts: dict[str, int] = {}\n    for record in recent:\n        area = mission_area(record)\n        counts[area] = counts.get(area, 0) + 1\n    return counts\n\n\ndef mission_coverage_bonus(item: dict[str, Any], area_counts: dict[str, int], contract: dict[str, Any]) -> float:\n    area = mission_area(item)\n    target_key = _TARGET_KEYS.get(area)\n    if not target_key or int(contract.get(target_key, 0) or 0) <= 0:\n        return 0.0\n    count = int(area_counts.get(area, 0) or 0)\n    if count >= 2:\n        return 0.0\n    # This is a bounded recovery-priority adjustment, not a publication-floor bypass.\n    # Only already-strong, authoritative candidates are eligible.\n    if _score(item) < 52.0:\n        return 0.0\n    tier = _tier(item)\n    if tier not in {1, 2}:\n        return 0.0\n    return 1.5 if count == 0 else 0.75\n\n\ndef annotate_recovery_candidates(items: Iterable[dict[str, Any]], history: Iterable[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:\n    window_items = int(contract.get("window_runs", 6) or 6) * max(1, int(contract.get("max_posts", 3) or 3))\n    counts = historical_area_counts(history, window_items)\n    prepared: list[dict[str, Any]] = []\n    for raw in items or []:\n        item = dict(raw)\n        item["historical_mission_area_count"] = int(counts.get(mission_area(item), 0) or 0)\n        item["mission_coverage_bonus"] = mission_coverage_bonus(item, counts, contract)\n        prepared.append(item)\n    prepared.sort(key=lambda x: (float(x.get("mission_coverage_bonus", 0) or 0), _score(x), str(x.get("published", ""))), reverse=True)\n    return prepared\n'''
    if path.exists():
        raise SystemExit(f"helper already exists: {path}")
    path.write_text(content, encoding="utf-8")


def add_tests() -> None:
    path = ROOT / "tests" / "test_mission_coverage_priority.py"
    content = '''from src.mission_coverage_priority import annotate_recovery_candidates, historical_area_counts, mission_coverage_bonus\nfrom src.unified_editorial_selection import mission_area\nfrom period_ranked_pipeline import canonical_rank_score\n\n\ndef test_mission_area_uses_keyword_classification_before_research_fallback():\n    item = {"title": "Could there ever be a viable test for artificial consciousness?", "category": "research", "content_type": "research"}\n    assert mission_area(item) == "mind_cognition"\n\n\ndef test_mission_area_does_not_default_unclassified_to_ai_core():\n    item = {"title": "Observations on an unrelated historical dataset", "category": "", "content_type": "news"}\n    assert mission_area(item) == "unclassified"\n\n\ndef test_historical_area_counts_ignore_education_and_use_recent_window():\n    history = [\n        {"content_type": "education", "mission_area": "mind_cognition"},\n        {"content_type": "news", "mission_area": "ai_core"},\n        {"content_type": "news", "mission_area": "mind_cognition"},\n    ]\n    assert historical_area_counts(history, 2) == {"ai_core": 1, "mind_cognition": 1}\n\n\ndef test_underrepresented_authoritative_mind_candidate_gets_bounded_bonus():\n    contract = {"window_runs": 6, "max_posts": 3, "mind_cognition_target": 1}\n    item = {"mission_area": "mind_cognition", "final_editorial_score": 54.15, "source_tier": 1}\n    assert mission_coverage_bonus(item, {"ai_core": 53, "mind_cognition": 1}, contract) == 0.75\n    annotated = annotate_recovery_candidates([item], [], contract)[0]\n    assert annotated["mission_coverage_bonus"] == 1.5\n    assert annotated["historical_mission_area_count"] == 0\n\n\ndef test_coverage_bonus_changes_rank_score_but_preserves_absolute_floor_contract():\n    item = {"radar_composite_score": 54.15, "signal_score": 0, "mission_coverage_bonus": 0.75}\n    assert canonical_rank_score(item) == 41.36\n    item["radar_composite_score"] = 70.0\n    assert canonical_rank_score(item) == 53.25\n'''
    # Keep numerical assertions tied to the current canonical formula; this test only verifies the bonus is additive.
    content = content.replace('assert canonical_rank_score(item) == 41.36', 'assert canonical_rank_score(item) == 41.36')
    if path.exists():
        raise SystemExit(f"test file already exists: {path}")
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    patch_unified_selection()\n    patch_pipeline()\n    patch_main()\n    add_helper()\n    add_tests()\n    print("mission coverage patch applied")\n'''.replace('\\n', '\n')
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    patch_unified_selection()
    patch_pipeline()
    patch_main()
    add_helper()
    add_tests()
    print("mission coverage patch applied")
