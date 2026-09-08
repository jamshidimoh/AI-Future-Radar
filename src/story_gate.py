"""Canonical Story Gate and canonical score boundary."""
from future_significance import annotate_future_significance, is_low_future_value
from editorial_score_v2 import score_editorial_v2
from story_identity import deduplicate_stories
from technology_signal_v2 import calculate_technology_signal_score

_TECH_SIGNAL_TERMS = (
    "artificial intelligence", "ai", "machine learning", "deep learning", "llm", "agi",
    "openai", "anthropic", "deepmind", "gpt", "claude", "gemini", "qwen", "llama",
    "reasoning model", "foundation model", "frontier model", "ai agent", "agentic ai",
    "robotics", "humanoid", "physical ai", "computer use", "ai safety", "ai security",
    "ai governance", "ai policy", "ai regulation", "ai infrastructure", "ai chip", "gpu",
    "npu", "tpu", "ai accelerator", "quantum computing", "quantum ai", "brain-computer interface",
    "bci", "neurotechnology", "synthetic biology", "protein design", "computational biology",
    "photonic computing", "neuromorphic", "technology", "computing", "digital transformation",
    "هوش مصنوعی", "یادگیری ماشین", "یادگیری عمیق", "مدل زبانی", "عامل هوشمند", "رباتیک",
    "فناوری", "رایانش", "محاسبات", "کوانتوم", "رابط مغز و رایانه",
)


def _technology_relevant(item):
    if item.get("ai_relevance") is True or item.get("_ai_link") is True:
        return True
    text = " ".join(
        str(item.get(k) or "")
        for k in ("title", "summary", "description", "category", "topic_family", "content_type")
    ).casefold()
    return any(term.casefold() in text for term in _TECH_SIGNAL_TERMS)


def _prepare_canonical_scores(item):
    candidate = dict(item)
    legacy_editorial = candidate.get("editorial_score")
    legacy_signal = candidate.get("signal_score")
    v2_editorial, features = score_editorial_v2(candidate)
    candidate["editorial_score_legacy"] = legacy_editorial
    candidate["signal_score_legacy"] = legacy_signal
    candidate["editorial_score_v2"] = v2_editorial
    candidate["editorial_features_v2"] = features
    candidate["editorial_score_pre_signal"] = v2_editorial
    vector = candidate.get("signal_vector") or {}
    if vector:
        signal_v2 = calculate_technology_signal_score(vector)
    else:
        try:
            signal_v2 = float(legacy_signal or 0)
        except (TypeError, ValueError):
            signal_v2 = 0.0
    candidate["technology_signal_score"] = round(signal_v2, 2)
    candidate["signal_score"] = candidate["technology_signal_score"]
    return candidate


def story_representative_rank_key(item):
    try:
        representative_score = float(item.get("editorial_score_pre_signal", item.get("editorial_score", 0)) or 0)
    except (TypeError, ValueError):
        representative_score = 0.0
    return (
        int(item.get("leader_priority", 0) or 0),
        int(item.get("leader_source_authority", 0) or 0),
        1 if item.get("protected_content") else 0,
        representative_score,
        str(item.get("published", "")),
    )


def _canonical_final_editorial_score(item):
    try:
        editorial = float(item.get("radar_composite_score", item.get("editorial_score_pre_signal", 0)) or 0)
    except (TypeError, ValueError):
        editorial = 0.0
    try:
        signal = float(item.get("technology_signal_score", item.get("signal_score", 0)) or 0)
    except (TypeError, ValueError):
        signal = 0.0
    return round(0.75 * editorial + 0.25 * signal, 2)


def gate_story_candidates(protected_items, leader_items, regular_items, seen_signatures, threshold=0.45):
    """Prepare canonical scores, filter low-information and invalid protected leaders, then deduplicate."""
    ordered = []
    for pool in (protected_items or [], leader_items or [], regular_items or []):
        prepared_items = []
        for raw in pool:
            item = dict(raw)
            if item.get("protected_content") and not _technology_relevant(item):
                item["protected_content"] = False
                item["leader_watch_protected"] = False
                item["protected_reason"] = "leader_protection_not_technology_relevant"
                print(
                    f"[Leader Protection Gate] dropped non-technology protected item: {str(item.get('title', ''))[:120]}",
                    flush=True,
                )
                continue
            prepared_items.append(_prepare_canonical_scores(item))
        ordered.extend(sorted(prepared_items, key=story_representative_rank_key, reverse=True))

    filtered = []
    for item in ordered:
        if is_low_future_value(item):
            continue
        annotate_future_significance(item)
        filtered.append(item)

    survivors = deduplicate_stories(filtered, history=list(seen_signatures or []))
    for item in survivors:
        item["final_editorial_score"] = _canonical_final_editorial_score(item)
        item["story_representative_score"] = story_representative_rank_key(item)[3]
    return survivors
