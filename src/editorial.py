"""Editorial orchestration with explicit mind/cognition and interview recall protection."""
from __future__ import annotations

import re

from src.editorial_core import classify_editorial_item as _classify_editorial_item
from src.editorial_core import contract_summary, enrich_items as _enrich_items, filter_ai_relevance as _filter_ai_relevance, filter_low_signal
from src.future_significance import annotate_future_significance
from src.interview_evidence import has_interview_evidence
from src.strategic_signal import strategic_forecast_score
from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio

_AI_BRIDGE_TERMS = (
    "Claude", "GPT", "Gemini", "Qwen", "Llama", "DeepSeek", "Mistral", "OpenAI", "Anthropic", "DeepMind",
    "transformer", "neural network", "reasoning model", "large language model", "artificial intelligence",
    "machine learning", "AGI", "ai consciousness", "ai philosophy", "ai cognition", "ai mind",
    "ai governance", "ai policy", "ai safety", "ai security", "ai agents", "agentic ai", "ai alignment", "ai regulation",
    "هوش مصنوعی", "هوشِ مصنوعی", "یادگیری ماشین", "یادگیری عمیق", "مدل زبانی بزرگ", "مدل بنیادی", "عامل هوشمند",
    "حکمرانی هوش مصنوعی", "سیاست‌گذاری هوش مصنوعی", "فلسفه هوش مصنوعی", "آگاهی مصنوعی", "هوش ماشین"
)
_MIND_TERMS = (
    "consciousness", "machine consciousness", "AI consciousness", "artificial consciousness", "sentience", "qualia",
    "self-awareness", "awareness", "cognitive science", "cognition", "cognitive", "mind", "brain", "neuroscience",
    "computational neuroscience", "predictive processing", "active inference", "global workspace", "integrated information",
    "philosophy of mind", "philosophy of science", "philosophy of technology", "philosophy of AI", "epistemology of AI",
    "technology and consciousness", "machine awareness", "science and technology studies", "آگاهی", "خودآگاهی", "شناخت",
    "علوم شناختی", "ذهن", "فلسفه ذهن", "فلسفه علم", "فلسفه فناوری", "فلسفه هوش مصنوعی", "معرفت شناسی", "معرفت‌شناسی",
    "علوم اعصاب", "مغز"
)
_INTERVIEW_TERMS = (
    "interview", "conversation", "fireside", "keynote", "podcast", "discussion", "q&a", "talk with", "speaks with",
    "in conversation", "sits down with", "مصاحبه", "گفتگو", "گفت‌وگو"
)
_EARLY_STRATEGIC_TERMS = (
    "ai governance", "ai policy", "ai regulation", "artificial intelligence regulation", "technology policy", "digital policy",
    "frontier model", "ai safety", "ai security", "ai agents", "agentic ai", "ai infrastructure", "ai chip", "ai data center",
    "هوش مصنوعی", "حکمرانی هوش مصنوعی", "سیاست‌گذاری هوش مصنوعی", "تنظیم‌گری هوش مصنوعی"
)
_CONSEQUENTIAL_TERMS = (
    "breach", "hack", "hacked", "security incident", "safety incident", "rogue agent", "misuse", "shutdown", "recall",
    "regulatory action", "critical vulnerability", "data leak", "agent hijack"
)
_EMERGING_TERMS = (
    "quantum computing", "quantum computer", "quantum chip", "qubit", "brain-computer interface", "bci", "neurotechnology",
    "humanoid robot", "physical ai", "robot foundation model", "ai accelerator", "gpu", "npu", "tpu", "photonic computing",
    "neuromorphic", "synthetic biology", "protein design", "computational biology"
)


def _evidence_text(item: dict) -> str:
    fields = ("title", "summary", "description", "evidence_text", "tags", "keywords")
    return " ".join(str(item.get(k) or "") for k in fields).casefold()


def _has_any(text: str, terms) -> bool:
    for term in terms:
        normalized = str(term).casefold()
        if normalized in {"ai", "agi"}:
            if re.search(rf"\b{re.escape(normalized)}\b", text, re.I):
                return True
        elif normalized in text:
            return True
    return False


def _is_mind_lane_candidate(item: dict, text: str) -> bool:
    category = str(item.get("category") or "").casefold()
    area = str(item.get("mission_area") or "").casefold()
    mind_signal = _has_any(text, _MIND_TERMS) or category == "mind" or area == "mind_cognition"
    return mind_signal and _has_any(text, _AI_BRIDGE_TERMS)


def _is_specialist_interview(item: dict, text: str) -> bool:
    interview = str(item.get("content_type") or "").casefold() == "interview" or _has_any(text, _INTERVIEW_TERMS)
    if not interview:
        return False
    return _has_any(text, _AI_BRIDGE_TERMS) and (
        _has_any(text, _MIND_TERMS)
        or str(item.get("category") or "").casefold() in {"ai", "mind", "future"}
        or str(item.get("mission_area") or "").casefold() in {"mind_cognition", "future_governance"}
    )


def _leader_interview(item: dict) -> bool:
    return bool(item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("is_leader")) and has_interview_evidence(item)


def _early_reason(item: dict, text: str) -> str:
    if _leader_interview(item):
        return "leader_interview"
    if _is_mind_lane_candidate(item, text):
        return "mind_cognition_lane"
    if _is_specialist_interview(item, text):
        return "specialist_interview"
    if _has_any(text, _EARLY_STRATEGIC_TERMS) and (_has_any(text, _AI_BRIDGE_TERMS) or str(item.get("category") or "").casefold() in {"ai", "future"}):
        return "strategic_ai_or_tech"
    if _has_any(text, _CONSEQUENTIAL_TERMS) and _has_any(text, _AI_BRIDGE_TERMS + _EARLY_STRATEGIC_TERMS):
        return "consequential_ai_or_tech"
    if _has_any(text, _EMERGING_TERMS):
        try:
            tier = int(item.get("source_tier") or 3)
        except (TypeError, ValueError):
            tier = 3
        if tier in {1, 2} or item.get("curated_discovery"):
            return "emerging_technology"
    return ""


def classify_editorial_item(item, prior=None):
    result = dict(_classify_editorial_item(item, prior or {}))
    named = str(result.get("leader") or item.get("leader") or item.get("watch_person") or "").strip()
    if item.get("is_leader_watch") or item.get("leader_watch_protected"):
        result["leader"] = named
        result["leader_signal"] = True
        if named and has_interview_evidence({**item, **result}):
            result.update(interview_signal=True, editorial_class="leader_interview", editorial_confidence=1.0)
        elif not named:
            result.update(editorial_class="fallback", editorial_confidence=0.35)
    return result


def enrich_items(items, leader_priorities, source_history=None, policy=None):
    enriched = _enrich_items(items, leader_priorities, source_history, policy)
    for item in enriched:
        if item.get("is_leader_watch") or item.get("leader_watch_protected"):
            item["leader_signal"] = True
            if item.get("leader") and has_interview_evidence(item):
                item["leader_watch_protected"] = True
            elif not item.get("leader"):
                item["editorial_slot"] = "fallback"
                item["editorial_class"] = "fallback"
    return enriched


def _prepare_relevance_item(raw: dict, supplied_keywords: tuple[str, ...]) -> tuple[dict, bool]:
    item = dict(raw)
    evidence = str(item.get("evidence_text") or "").strip()
    if evidence:
        item["description"] = " ".join(part for part in (item.get("description"), evidence) if part).strip()
    text = _evidence_text(item)
    bridge_hits = _has_any(text, _AI_BRIDGE_TERMS) or _has_any(text, supplied_keywords)
    reason = _early_reason(item, text)
    curated = bool(item.get("curated_discovery") and item.get("preferred_source") and int(item.get("source_tier") or 3) in {1, 2})
    if reason and bridge_hits:
        item.update(
            early_inclusion=True,
            early_inclusion_reason=reason,
            relevance_reason=f"early_inclusion:{reason}",
            _ai_link=True,
            ai_relevance=True,
            ai_relevance_confidence=0.90 if reason == "mind_cognition_lane" else 0.85,
            evidence_strength=max(float(item.get("evidence_strength", 0) or 0), 8.5),
            ai_relevance_quality="protected_mission_lane",
        )
        if _is_mind_lane_candidate(item, text):
            item["mission_area"] = "mind_cognition"
            item["topic_family"] = "consciousness_cognition"
        else:
            item["topic_family"] = "ai_core"
        return item, True
    item["_curated_trusted_ai_bridge"] = curated
    item["_has_direct_ai_evidence"] = bridge_hits
    return item, False


def _accept_trusted_curated(normalized: list[dict], result: list[dict]) -> None:
    present = {str(x.get("title") or "") for x in result}
    for item in normalized:
        if not item.get("_curated_trusted_ai_bridge") or item.get("_has_direct_ai_evidence"):
            continue
        title = str(item.get("title") or "")
        if title in present:
            continue
        accepted = dict(item)
        accepted.update(_ai_link=True, relevance_reason="curated_ai_provenance", topic_family="ai_core", relevance_evidence=["curated AI provenance"], evidence_level="B", ai_relevance_confidence=0.55, evidence_strength=5.5, ai_relevance_quality="bridge")
        result.append(accepted)


def _finalize_relevance_confidence(result) -> None:
    for item in result:
        if item.get("relevance_reason") == "curated_ai_provenance" or item.get("early_inclusion"):
            continue
        evidence = str(item.get("evidence_text") or "").strip()
        confidence = 0.95 if evidence else 0.85
        item["ai_relevance_confidence"] = confidence
        item["evidence_strength"] = max(float(item.get("evidence_strength", 0) or 0), confidence * 10.0)
        item["ai_relevance_quality"] = "high" if confidence >= 0.90 else "medium"


def filter_ai_relevance(items, ai_keywords=None):
    normalized, rescue = [], []
    supplied = tuple(str(x) for x in (ai_keywords or ()) if str(x).strip())
    for raw in items or []:
        item, rescued = _prepare_relevance_item(raw, supplied)
        (rescue if rescued else normalized).append(item)
    keywords = list(dict.fromkeys(list(ai_keywords or []) + list(_AI_BRIDGE_TERMS)))
    result = _filter_ai_relevance(
        [x for x in normalized if not x.get("_force_reject_ai_gate") and (not x.get("_curated_trusted_ai_bridge") or x.get("_has_direct_ai_evidence"))],
        keywords,
    )
    _accept_trusted_curated(normalized, result)
    result.extend(rescue)
    _finalize_relevance_confidence(result)
    print(
        f"[Early Inclusion] rescued={len(rescue)} | mind_lane={sum(x.get('early_inclusion_reason') == 'mind_cognition_lane' for x in rescue)} | interviews={sum(x.get('early_inclusion_reason') in {'specialist_interview','leader_interview'} for x in rescue)} | direct/curated={len(result)-len(rescue)}",
        flush=True,
    )
    return result


def _apply_strategic_signal(item):
    strategic = strategic_forecast_score(item)
    item["mission_score_base"] = round(float(item.get("mission_score", 0) or 0), 2)
    item["mission_score"] = round(float(item.get("mission_score", 0) or 0) + strategic, 2)
    return item


def _annotate_selection_value(item):
    annotate_future_significance(item)
    item["final_editorial_score"] = item["radar_composite_score"]
    return item


def select_editorial(items, max_posts=4, max_per_source=2, max_per_type=2, policy=None):
    policy = policy or {}
    protected_limit = int(policy.get("protected_slots", policy.get("leader_interview_slots", 2)) or 0)
    protected, regular, seen = [], [], set()
    for raw in items or []:
        item = dict(raw)
        name = str(item.get("leader") or item.get("watch_person") or "").strip().casefold()
        if (item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("leader_signal")) and name:
            if name in seen:
                continue
            seen.add(name)
            protected.append(item)
        else:
            regular.append(item)
    protected.sort(key=lambda x: (int(x.get("leader_priority", 0) or 0), float(x.get("editorial_score", 0) or 0), str(x.get("published", ""))), reverse=True)
    protected = protected[:protected_limit]
    for item in protected:
        interviewed = has_interview_evidence(item)
        item["editorial_slot"] = "leader_interview" if interviewed else "fallback"
        item["editorial_class"] = "leader_interview" if interviewed else item.get("editorial_class", "leader_activity")
        item["leader_watch_protected"] = True
        item["leader_signal"] = True
        item["selection_reason"] = f"protected:{item.get('leader') or item.get('watch_person')}"
    for item in regular:
        _annotate_selection_value(item)
    selected_regular = select_regular_portfolio(
        regular,
        max_posts=max_posts,
        max_per_source=max_per_source,
        max_per_type=max_per_type,
        contract=load_editorial_contract(),
        mission_aware=bool(policy.get("mission_aware", True)),
        strict_relevance=bool(policy.get("strict_relevance", False)),
    )
    for item in selected_regular:
        if item.get("mission_area") == "mind_cognition":
            item["selection_lane"] = "mind_cognition_protected"
        if item.get("interview_signal") or str(item.get("content_type") or "").casefold() == "interview":
            item["selection_lane"] = item.get("selection_lane", "interview")
    return protected + selected_regular


__all__ = [
    "_apply_strategic_signal", "classify_editorial_item", "contract_summary", "enrich_items",
    "filter_ai_relevance", "filter_low_signal", "select_editorial",
]
