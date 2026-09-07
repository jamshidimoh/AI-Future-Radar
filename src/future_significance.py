"""Future-significance scoring for AI Future Radar.

This layer is deliberately separate from mission relevance and evidence quality.
It estimates whether a candidate contributes meaningful information about
technological trajectory, capability change, and future impact.
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
    fields = (
        "title", "summary", "description", "why_it_matters", "evidence_text",
        "content_type", "editorial_class", "category", "mission_area",
        "topic_family", "tags", "keywords",
    )
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

    content_type = str(item.get("content_type") or "").casefold()
    editorial_class = str(item.get("editorial_class") or "").casefold()
    topic_family = str(item.get("topic_family") or "").casefold()

    if item.get("research_signal") or content_type in {"research", "paper", "study", "preprint"}:
        features["research_depth"] = max(features.get("research_depth", 0.0), 0.67)
    if editorial_class in {"research_breakthrough", "convergence_signal"}:
        features["breakthrough"] = max(features.get("breakthrough", 0.0), 0.67)
    if editorial_class == "major_industry_news":
        features["strategic_implication"] = max(features.get("strategic_implication", 0.0), 0.67)
    if topic_family in {"quantum_ai", "consciousness_cognition", "future_technology", "bio_ai", "bci_neuro_ai", "robotics_embodied", "computing_infrastructure"}:
        features["cross_domain_impact"] = max(features.get("cross_domain_impact", 0.0), 0.67)
    if item.get("strategic_forecast_signal"):
        features["future_horizon"] = max(features.get("future_horizon", 0.0), 0.67)
        features["strategic_implication"] = max(features.get("strategic_implication", 0.0), 0.67)

    low_markers = cfg.get("low_value_markers", []) or []
    low_hits = _hits(text, low_markers)
    features["low_value_hits"] = float(low_hits)
    features["low_value_penalty"] = min(float(cfg.get("low_value_penalty_cap", 0.30) or 0.30), low_hits * 0.10)

    high_signal_dimensions = (
        "capability_shift", "breakthrough", "cross_domain_impact",
        "strategic_implication", "research_depth", "human_societal_impact",
        "future_horizon", "insight_density",
    )
    features["substantive_signal"] = max((features.get(k, 0.0) for k in high_signal_dimensions), default=0.0)
    return features


def is_low_future_value(item: dict[str, Any]) -> bool:
    """Reject only explicit utility/tutorial stories lacking a compensating signal.

    This is intentionally narrow. It does not reject ChatGPT/OpenAI/product news
    merely because of the product name; a capability shift, research result,
    strategic consequence, convergence signal, or strong future implication keeps
    the story eligible.
    """
    cfg = _load_policy().get("future_significance", {})
    if not bool(cfg.get("enabled", True)):
        return False
    features = build_future_features(item)
    if features.get("low_value_hits", 0) <= 0:
        return False
    protected_classes = {"leader_interview", "research_breakthrough", "convergence_signal"}
    if str(item.get("editorial_class") or "").casefold() in protected_classes:
        return False
    if item.get("research_signal") or item.get("interview_signal"):
        return False
    return features.get("substantive_signal", 0.0) < 0.34


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
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    top = sorted(counts, key=lambda x: (-counts[x], x))[:5]
    area = str(item.get("mission_area") or "ai_core").casefold()
    return area + ":" + ",".join(top)
