# ruff: noqa: I001
"""History-aware topic repetition guard for editorial publication.

This guard is intentionally separate from same-story deduplication. It prevents
different URLs that are materially about the same recent topic from crowding the
feed, while leaving genuinely new developments eligible.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.event_identity import has_material_update
from src.semantic_dedup import _similarity, get_story_signature


_THEME_FAMILIES: dict[str, set[str]] = {
    "ai_safety_risk": {
        "risk", "safety", "alignment", "superintelligence", "agi", "doom",
        "catastrophic", "control", "pause", "pausing", "slowdown", "slow",
        "danger", "existential", "ایمنی", "ریسک", "خطر", "فاجعه", "کنترل",
        "توقف", "کندکردن", "ابرهوش", "هم‌ترازی", "همترازی",
    },
    "model_release_evaluation": {
        "model", "models", "release", "released", "launch", "launched",
        "benchmark", "evaluation", "eval", "capability", "capabilities",
        "مدل", "معرفی", "عرضه", "ارزیابی", "آزمون", "بنچمارک", "قابلیت",
    },
    "agents": {
        "agent", "agents", "agentic", "ai_agents", "autonomous", "browser",
        "computer_use", "tool", "tools", "عامل", "عامل‌های", "خودمختار",
        "خودکار", "رایانه",
    },
    "robotics_physical_ai": {
        "robotics", "robot", "humanoid", "physical", "embodied", "manufacturing",
        "robotic", "رباتیک", "ربات", "انسان‌نما", "فیزیکی", "مجسم",
    },
    "quantum": {
        "quantum", "quantum_computing", "qubit", "error_correction",
        "کوانتوم", "کیوبیت", "محاسبات",
    },
    "mind_consciousness": {
        "consciousness", "cognition", "mind", "sentience", "self", "brain",
        "neuroscience", "آگاهی", "شناخت", "ذهن", "هوشیاری", "مغز", "علوم",
    },
    "bci_neuro": {
        "bci", "brain-computer", "neurotechnology", "neural", "interface",
        "رابط", "عصبی", "نوروتکنولوژی", "مغز-رایانه",
    },
    "bio_genomics": {
        "genetics", "genomics", "crispr", "protein", "synthetic", "biology",
        "gene", "زیست", "ژنتیک", "ژنوم", "کریسپر", "پروتئین",
    },
    "chips_infrastructure": {
        "chip", "chips", "semiconductor", "gpu", "accelerator", "compute",
        "inference", "datacenter", "hardware", "تراشه", "نیمه‌هادی",
        "شتاب‌دهنده", "محاسبات", "سخت‌افزار", "دیتاسنتر",
    },
    "governance_policy": {
        "governance", "policy", "regulation", "regulatory", "law", "laws",
        "government", "senate", "eu", "حکمرانی", "سیاست",
        "مقررات", "قانون", "دولت", "نهاد",
    },
    "education_work": {
        "education", "learning", "school", "university", "teacher", "student",
        "jobs", "employment", "workforce", "labor", "آموزش", "دانشگاه",
        "دانشجو", "معلم", "اشتغال", "کار", "نیروی",
    },
}


def _signature(value: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(value, dict):
        return get_story_signature(value)
    return get_story_signature(str(value or ""))


def _anchor_overlap(left: dict[str, Any], right: dict[str, Any]) -> int:
    return len(set(left.get("anchors") or []) & set(right.get("anchors") or []))


def _topic_score(item: dict[str, Any], prior: dict[str, Any] | str) -> tuple[float, int]:
    candidate = get_story_signature(item)
    stored = _signature(prior)
    return _similarity(candidate, stored), _anchor_overlap(candidate, stored)


def _topic_family(value: dict[str, Any] | str) -> tuple[str, int]:
    sig = _signature(value)
    if isinstance(value, dict):
        raw_text = " ".join(
            str(value.get(key) or "")
            for key in ("title", "summary", "description", "content", "why_it_matters", "why", "leader", "watch_person")
        )
    else:
        raw_text = str(value or "")
    searchable = f"{raw_text} {' '.join(str(x) for x in sig.get('context') or [])}".casefold()
    best_family = ""
    best_hits = 0
    for family, terms in _THEME_FAMILIES.items():
        hits = sum(1 for term in terms if str(term).casefold() in searchable)
        if hits > best_hits:
            best_family, best_hits = family, hits
    return best_family, best_hits


def _reconstruct_prior(prior: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(prior, dict):
        return prior
    sig = _signature(prior)
    return {
        "title": str(sig.get("title_text") or ""),
        "summary": " ".join(str(x) for x in (sig.get("context") or [])),
        "leader": str(sig.get("leader") or ""),
    }


def _topic_conflict(
    item: dict[str, Any],
    prior: dict[str, Any] | str,
    *,
    semantic_threshold: float,
) -> tuple[bool, float, int, str]:
    score, anchors = _topic_score(item, prior)
    family, hits = _topic_family(item)
    prior_family, prior_hits = _topic_family(prior)
    same_family = bool(family and family == prior_family)
    strong_semantic = score >= semantic_threshold and anchors >= 1
    thematic_conflict = same_family and hits >= 2 and prior_hits >= 2
    return strong_semantic or thematic_conflict, score, anchors, family if same_family else ""


def _material_update_or_keep(item: dict[str, Any], prior: dict[str, Any] | str) -> bool:
    try:
        return has_material_update(item, _reconstruct_prior(prior))
    except Exception:
        return False


def find_topic_repetition(
    item: dict[str, Any],
    history: Iterable[dict[str, Any] | str],
    *,
    threshold: float = 0.68,
    soft_threshold: float = 0.62,
    min_anchor_overlap: int = 2,
) -> tuple[float, str]:
    """Return the strongest recent story/topic repetition score."""
    best_score = 0.0
    best_title = ""
    for prior in history or ():
        score, anchors = _topic_score(item, prior)
        family, hits = _topic_family(item)
        prior_family, prior_hits = _topic_family(prior)
        same_family = bool(family and family == prior_family and hits >= 2 and prior_hits >= 2)
        qualifies = (
            (score >= soft_threshold and anchors >= min_anchor_overlap)
            or (same_family and score >= 0.23)
        )
        if qualifies and score >= best_score:
            best_score = score
            best_title = str(_signature(prior).get("title_text") or "").strip()
    return best_score, best_title


def filter_topic_repetition(
    items: Iterable[dict[str, Any]],
    history: Iterable[dict[str, Any] | str],
    *,
    current_items: Iterable[dict[str, Any]] | None = None,
    window: int = 24,
    threshold: float = 0.68,
    soft_threshold: float = 0.62,
    min_anchor_overlap: int = 2,
) -> tuple[list[dict[str, Any]], int]:
    """Filter repeated topics across recent history and already selected items."""
    materialized = list(items or ())
    recent = list(history or ())[-max(0, int(window)):] if window else []
    current = list(current_items or ())
    if not recent and not current:
        return materialized, 0

    kept: list[dict[str, Any]] = []
    blocked = 0
    comparison_pool: list[dict[str, Any] | str] = []
    comparison_pool.extend(recent)
    comparison_pool.extend(current)

    for item in materialized:
        best = (0.0, "", None)
        for prior in comparison_pool:
            matches, score, anchors, _ = _topic_conflict(
                item,
                prior,
                semantic_threshold=soft_threshold,
            )
            family_match = bool(
                _topic_family(item)[0]
                and _topic_family(item)[0] == _topic_family(prior)[0]
            )
            if not matches or (score < soft_threshold and not family_match):
                continue
            if score > best[0]:
                best = (score, str(_signature(prior).get("title_text") or ""), prior)
        if best[2] is not None:
            strong_block = best[0] >= threshold and (best[1] or best[0] >= soft_threshold)
            same_family_soft = (
                _topic_family(item)[0]
                and _topic_family(item)[0] == _topic_family(best[2])[0]
                and best[0] >= 0.15
                and _topic_family(item)[1] >= 2
                and _topic_family(best[2])[1] >= 2
            )
            if strong_block or same_family_soft:
                if _material_update_or_keep(item, best[2]):
                    kept.append(item)
                    continue
                blocked += 1
                print(
                    "[Topic Repetition Guard] blocked "
                    f"score={best[0]:.3f} family={_topic_family(item)[0] or '-'} "
                    f"matched={best[1][:100]} title={str(item.get('title') or '')[:120]}",
                    flush=True,
                )
                continue
        kept.append(item)
        comparison_pool.append(item)

    print(
        "[Topic Repetition Guard] "
        f"checked={len(materialized)} blocked={blocked} remaining={len(kept)} "
        f"window={len(recent)} current={len(current)} threshold={threshold:.2f}",
        flush=True,
    )
    return kept, blocked


def filter_history_topic_repetition(
    items: Iterable[dict[str, Any]],
    history: Iterable[dict[str, Any] | str],
    *,
    window: int = 24,
    threshold: float = 0.66,
    soft_threshold: float = 0.60,
    min_anchor_overlap: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    return filter_topic_repetition(
        items,
        history,
        current_items=None,
        window=window,
        threshold=threshold,
        soft_threshold=soft_threshold,
        min_anchor_overlap=min_anchor_overlap,
    )
