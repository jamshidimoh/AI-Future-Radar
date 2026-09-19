"""TypeSafe semantic judgment layer for bounded editorial reranking.

This module is deliberately fail-open for production safety:
- off: no TypeSafe calls and no behavior change.
- audit: call TypeSafe, record/log the proposed ordering, but keep the existing order.
- active: reorder only the bounded candidate pool supplied by the caller.

Code remains authoritative for hard publication policy, quotas, diversity, safety,
deduplication, and delivery. TypeSafe supplies semantic judgment only.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Protocol, Sequence

logger = logging.getLogger(__name__)

MODE_ENV = "AI_RADAR_TYPESAFE_RERANK_MODE"
API_KEY_ENV = "TYPESAFE_API_KEY"
DEFAULT_MODE = "off"

TS_WEIGHT_ENV = "AI_RADAR_TYPESAFE_RERANK_WEIGHT"
DEFAULT_TYPESAFE_WEIGHT = 0.20

_SCORE_LEVELS = (
    "0: no meaningful evidence for this dimension",
    "1: weak evidence; mostly incidental or generic",
    "2: moderate evidence; useful but not distinctive",
    "3: strong evidence; clearly useful to the radar mission",
    "4: exceptional evidence; directly important and distinctive",
)

_RADAR_MISSION = (
    "AI-Future-Radar tracks credible, consequential developments in AI and "
    "advanced technology, including frontier models, agents, robotics, quantum, "
    "BCI/neurotechnology, AI-for-science/biotech, consciousness/cognitive science, "
    "future technology, and scientifically grounded interdisciplinary signals. "
    "Community/aggregator chatter is not a target. Publication policy remains in code."
)


class _SystemOneClient(Protocol):
    def system_one(self, *, state: dict[str, Any], questions: dict[str, Any]) -> Any: ...


def _mode() -> str:
    value = os.getenv(MODE_ENV, DEFAULT_MODE).strip().lower()
    return value if value in {"off", "audit", "active"} else DEFAULT_MODE


def _weight() -> float:
    try:
        value = float(os.getenv(TS_WEIGHT_ENV, DEFAULT_TYPESAFE_WEIGHT))
    except (TypeError, ValueError):
        return DEFAULT_TYPESAFE_WEIGHT
    return max(0.0, min(0.35, value))


def enabled() -> bool:
    """Return whether a live TypeSafe call should be attempted."""
    return _mode() in {"audit", "active"} and bool(os.getenv(API_KEY_ENV, "").strip())


def _state_for(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission": _RADAR_MISSION,
        "candidate": {
            "title": str(item.get("title") or ""),
            "summary": str(item.get("summary") or item.get("description") or ""),
            "why_it_matters": str(item.get("why_it_matters") or ""),
            "source": str(item.get("source") or item.get("source_name") or ""),
            "content_type": str(item.get("content_type") or ""),
            "category": str(item.get("category") or ""),
            "mission_area": str(item.get("mission_area") or ""),
            "leader": str(item.get("leader") or item.get("watch_person") or ""),
            "published": str(item.get("published") or ""),
        },
    }


def _score_question(label: str, dimension: str, positive: str) -> Any:
    from typesafe_sdk import Score

    return Score(
        instructions={
            "dimension": dimension,
            "task": (
                f"Score the candidate on {dimension}. Return the degree supported "
                "by the evidence in the supplied state, not whether you personally "
                "like the story."
            ),
            "positive_signal": positive,
            "labels": label,
        },
        criteria=_SCORE_LEVELS,
    )


def _answer_value(answer: Any) -> tuple[float, float]:
    raw_score = float(getattr(answer, "score", 0.0) or 0.0)
    score = max(0.0, min(1.0, raw_score / 4.0))
    confidence = float(getattr(answer, "confidence", 0.0) or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    return score, confidence


def _evaluate_item(item: dict[str, Any], client: _SystemOneClient) -> tuple[float, float, dict[str, float]]:
    response = client.system_one(
        state=_state_for(item),
        questions={
            "mission_fit": _score_question(
                "mission_fit",
                "fit with the radar's stated mission",
                "The story is directly relevant to one or more tracked AI/future technology domains.",
            ),
            "novelty": _score_question(
                "novelty",
                "novelty and information gain",
                "The story adds a consequential signal rather than repeating a familiar or generic point.",
            ),
            "editorial_value": _score_question(
                "editorial_value",
                "editorial value for a specialist Persian-language technology radar",
                "The story contains substantive evidence, a meaningful development, or a clear implication worth surfacing.",
            ),
        },
    )
    scores: dict[str, float] = {}
    confidences: list[float] = []
    for name in ("mission_fit", "novelty", "editorial_value"):
        score, confidence = _answer_value(response.scores[name])
        scores[name] = score
        confidences.append(confidence)
    judgment = (
        scores["mission_fit"] * 0.45
        + scores["novelty"] * 0.25
        + scores["editorial_value"] * 0.30
    )
    confidence = sum(confidences) / len(confidences)
    return judgment, confidence, scores


def rerank_candidates(
    items: Sequence[dict[str, Any]],
    *,
    client: _SystemOneClient | None = None,
) -> list[dict[str, Any]]:
    """Apply bounded TypeSafe semantic reranking without changing hard policy.

    The caller is expected to pass the already-bounded candidate window.
    Protected/special-lane items are left in their original relative positions;
    only ordinary candidates are eligible for semantic reranking.
    """
    original = list(items or [])
    mode = _mode()
    if mode == "off" or not original:
        return original
    if not os.getenv(API_KEY_ENV, "").strip():
        logger.info("[TypeSafe] mode=%s but %s is missing; fail-open", mode, API_KEY_ENV)
        return original

    try:
        if client is None:
            from typesafe_sdk import TypeSafeClient

            client = TypeSafeClient()
        eligible_indices = [
            index
            for index, item in enumerate(original)
            if not item.get("protected_slot")
            and not item.get("_rank_is_tier0")
            and not item.get("technical_trend_lane_selected")
            and not item.get("mind_lane_selected")
            and not item.get("voices_perspectives_lane_selected")
        ]
        if len(eligible_indices) < 2:
            return original

        judgments: list[tuple[float, float, dict[str, float], int]] = []
        for index in eligible_indices:
            judgment, confidence, dimensions = _evaluate_item(original[index], client)
            judgments.append((judgment, confidence, dimensions, index))
            item = original[index]
            item["typesafe_judgment_score"] = round(judgment, 4)
            item["typesafe_judgment_confidence"] = round(confidence, 4)
            item["typesafe_judgment_dimensions"] = {k: round(v, 4) for k, v in dimensions.items()}
            item["typesafe_rerank_applied"] = False

        # Existing order is an intentionally scale-free baseline: no assumption is
        # made about the magnitude of editorial_score/final_editorial_score.
        weight = _weight()
        count = len(judgments)
        ranked = []
        for position, (judgment, confidence, _, index) in enumerate(judgments):
            baseline = 1.0 if count == 1 else 1.0 - (position / (count - 1))
            effective_judgment = judgment * confidence
            combined = (1.0 - weight) * baseline + weight * effective_judgment
            ranked.append((combined, index))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))

        reordered_indices = [index for _, index in ranked]
        proposed = list(reordered_indices)
        original_eligible = eligible_indices

        if mode == "audit":
            changed = proposed != original_eligible
            logger.info(
                "[TypeSafe] audit candidates=%d changed=%s weight=%.3f",
                count,
                changed,
                weight,
            )
            return original

        rank_iter = iter(reordered_indices)
        result = list(original)
        for index in original_eligible:
            replacement_index = next(rank_iter)
            result[index] = original[replacement_index]
        for item in result:
            if item.get("typesafe_judgment_score") is not None:
                item["typesafe_rerank_applied"] = True
        logger.info(
            "[TypeSafe] active candidates=%d weight=%.3f order_changed=%s",
            count,
            weight,
            reordered_indices != original_eligible,
        )
        return result
    except Exception as exc:
        logger.warning("[TypeSafe] rerank failed; preserving existing order: %s", exc, exc_info=True)
        return original
