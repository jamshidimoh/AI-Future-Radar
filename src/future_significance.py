"""Future-significance scoring for AI Future Radar.

This layer is deliberately separate from mission relevance, evidence quality,
and technology signal scoring. It estimates whether a candidate contributes
meaningful information about technological trajectory and future change.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "future_significance_policy.yaml"


def _load_policy() -> dict[str, Any]:
    try:
        return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _text(item: dict[str, Any]) -> str:
    fields = ("title", "summary", "description", "content_type", "editorial_class", "category", "mission_area", "tags", "keywords")
    return " ".join(str(item.get(k) or "") for k in fields).casefold()


def _hits(text: str, markers: list[str]) -> int:
    return sum(1 for marker in markers if str(marker).casefold() in text)


def _norm_dimension(hits: int) -> float:
    return min(1.0, hits / 3.0)


def build_future_features(item: dict[str, Any]) -> dict[str, float]:
    cfg = _load_policy().get("future_significance", {})
    markers = cfg.get("high_value_markers", {}) or {}
    text = _text(item)
    features = {name: _norm_dimension(_hits(text, values or [])) for name, values in markers.items()}

    # Evidence-backed research and authoritative content get a modest floor,
    # but evidence itself remains owned by the evidence/editorial layers.
    if item.get("research_signal") or str(item.get("content_type") or "").casefold() in {"research", "paper", "study", "preprint"}:
        features["research_depth"] = max(features.get("research_depth", 0.0), 0.67)

    # Explicit editorial classes are useful semantic hints already produced by
    # the existing classifier; they do not bypass quality gates.
    cls = str(item.get("editorial_class") or "").casefold()
    if cls in {"research_breakthrough", "convergence_signal"}:
        features["breakthrough"] = max(features.get("breakthrough", 0.0), 0.67)
    if cls == "major_industry_news":
        features["strategic_implication"] = max(features.get("strategic_implication", 0.0), 0.67)

    low_markers = cfg.get("low_value_markers", []) or []
    low_hits = _hits(text, low_markers)
    features["low_value_penalty"] = min(float(cfg.get("low_value_penalty_cap", 0.20) or 0.20), low_hits * 0.08)
    return features


def score_future_significance(item: dict[str, Any]) -> tuple[float, dict[str, float]]:
    cfg = _load_policy().get("future_significance", {})
    dims = cfg.get("dimensions", {}) or {}
    features = build_future_features(item)
    raw = sum(float(dims.get(k, 0.0) or 0.0) * features.get(k, 0.0) for k in dims)
    score = max(0.0, min(100.0, raw * 100.0 - features.get("low_value_penalty", 0.0) * 100.0))
    return round(score, 2), features


def annotate_future_significance(item: dict[str, Any]) -> dict[str, Any]:
    score, features = score_future_significance(item)
    item["future_significance_score"] = score
    item["future_significance_features"] = features
    editorial = float(item.get("editorial_score_pre_signal", item.get("editorial_score", 0)) or 0.0)
    cfg = _load_policy().get("future_significance", {})
    ew = float(cfg.get("editorial_weight", 0.65) or 0.65)
    fw = float(cfg.get("future_weight", 0.35) or 0.35)
    item["radar_composite_score"] = round(editorial * ew + score * fw, 2)
    return item


def future_topic_fingerprint(item: dict[str, Any]) -> str:
    """Return a coarse deterministic topic fingerprint for diversity reranking."""
    text = _text(item)
    stop = {"the", "and", "for", "with", "from", "that", "this", "about", "into", "new", "ai", "model", "models"}
    tokens = [t for t in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text) if t not in stop]
    # Stable, compact fingerprint: top recurring tokens plus mission area.
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    top = sorted(counts, key=lambda x: (-counts[x], x))[:5]
    area = str(item.get("mission_area") or "ai_core").casefold()
    return area + ":" + ",".join(top)
