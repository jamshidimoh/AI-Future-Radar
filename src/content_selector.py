"""Deterministic editorial selection engine for AI Future Radar.

Selection protects high-value interviews and leader activity first, then fills
remaining slots using score, novelty and source/type diversity. Authoritative
sources receive a capped ranking boost rather than an unconditional override.
"""
from __future__ import annotations

import re
from collections import Counter

try:
    from .ranking_guard import filter_quality_candidates
except ImportError:
    from ranking_guard import filter_quality_candidates

INTERVIEW_TYPES = {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "qa", "q&a", "discussion"}
INTERVIEW_TERMS = {"interview", "conversation", "fireside", "keynote", "podcast", "episode", "discussion", "talk with", "talk to", "speaks with", "in conversation", "q&a", "dialogue", "interviewed by", "sits down with", "deep conversation"}
RESEARCH_TYPES = {"research", "paper", "study", "preprint"}
RESEARCH_TERMS = {"paper", "research", "study", "preprint", "scientific", "experiment", "findings", "peer reviewed", "peer-reviewed"}
NEWS_TYPES = {"news", "official", "product_news"}
AUTHORITATIVE_SOURCE_PRIORITIES = {"mit csail": 100, "building 32": 100, "cap.csail.mit.edu": 100, "stanford hai": 95, "stanford institute for human-centered ai": 95, "hai.stanford.edu": 95, "berkeley ai research": 95, "bair": 95, "bair.berkeley.edu": 95, "google deepmind": 90, "deepmind.google": 90, "openai": 90, "openai.com": 90, "anthropic": 90, "anthropic.com": 90, "mit news": 88, "news.mit.edu": 88, "nature": 88, "nature.com": 88, "quanta magazine": 82, "quantamagazine.org": 82, "carnegie mellon": 82, "cmu": 82, "cs.cmu.edu": 82}

def _text(item): return " ".join(str(item.get(k) or "") for k in ("title", "summary", "description")).lower()
def _has_term(text, term):
    term = str(term).lower().strip()
    if not term: return False
    if len(term) <= 5 and re.fullmatch(r"[a-z0-9]+", term): return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
    return term in text
def _has_any(text, terms): return any(_has_term(text, term) for term in terms)
def _authoritative_priority(item):
    haystack = " ".join(str(item.get(k) or "").lower() for k in ("source", "source_url", "url", "source_domain", "title"))
    return max((priority for marker, priority in AUTHORITATIVE_SOURCE_PRIORITIES.items() if marker in haystack), default=0)
def is_interview(item):
    ctype = str(item.get("content_type") or "").lower().strip(); source_type = str(item.get("source_type") or "").lower().strip(); source_name = str(item.get("source") or "").lower()
    return ctype in INTERVIEW_TYPES or bool(item.get("interview_signal")) or _has_any(_text(item), INTERVIEW_TERMS) or ("podcast" in source_type and ctype not in NEWS_TYPES) or ("podcast" in source_name and ctype not in NEWS_TYPES)
def is_research(item):
    ctype = str(item.get("content_type") or "").lower().strip()
    return ctype in RESEARCH_TYPES or bool(item.get("research_signal")) or _has_any(_text(item), RESEARCH_TERMS)
def is_news(item):
    ctype = str(item.get("content_type") or "").lower().strip()
    return ctype in NEWS_TYPES or bool(item.get("news_signal"))
def leader_name(item): return str(item.get("leader") or item.get("watch_person") or "").strip()
def class_of(item):
    leader, interview, research, news = leader_name(item), is_interview(item), is_research(item), is_news(item)
    if leader and interview: return "leader_interview"
    if research and not leader: return "research_breakthrough"
    if news and not research: return "major_industry_news"
    if item.get("trend_signal"): return "future_signal"
    return str(item.get("editorial_class") or "fallback")
def _score(item):
    base = float(item.get("editorial_score", 0) or 0); signal = float(item.get("signal_score", 0) or 0); leader = leader_name(item); interview = is_interview(item); auth = _authoritative_priority(item)
    auth_boost = min(12.0, auth * 0.12) if auth else 0.0
    item["authoritative_source_priority"] = auth
    return base + signal * 0.30 + (40 if interview and leader else 0) + (20 if leader else 0) + (8 if item.get("source_tier") == 1 else 0) + auth_boost + (4 if item.get("leader_activity_signal") else 0)

def select_content(items, max_posts=4, max_per_source=2, max_per_type=2, leader_slots=2):
    candidates = filter_quality_candidates(list(items or []))
    ranked = sorted(candidates, key=lambda x: (_score(x), float(x.get("editorial_confidence", 0) or 0)), reverse=True)
    selected, selected_ids, source_counts, type_counts, leaders = [], set(), Counter(), Counter(), set()
    def eligible(item, require_class=None):
        if id(item) in selected_ids or (require_class and class_of(item) != require_class): return False
        source, ctype = str(item.get("source") or "unknown"), str(item.get("content_type") or "news").lower()
        return _score(item) > 0 and source_counts[source] < max_per_source and type_counts[ctype] < max_per_type
    for _ in range(max(0, min(leader_slots, max_posts))):
        candidates = [x for x in ranked if eligible(x, "leader_interview") and leader_name(x) not in leaders]
        if not candidates: break
        item = max(candidates, key=_score); selected.append(item); selected_ids.add(id(item)); leaders.add(leader_name(item))
        source_counts[str(item.get("source") or "unknown")] += 1; type_counts[str(item.get("content_type") or "news").lower()] += 1
        item["editorial_slot"], item["selection_reason"] = "leader_interview", f"protected:leader_interview:{leader_name(item)}"
    for cls, slot in (("research_breakthrough", "research"), ("major_industry_news", "news")):
        if len(selected) >= max_posts: break
        candidates = [x for x in ranked if eligible(x, cls)]
        if not candidates: continue
        item = max(candidates, key=_score); selected.append(item); selected_ids.add(id(item))
        source_counts[str(item.get("source") or "unknown")] += 1; type_counts[str(item.get("content_type") or "news").lower()] += 1
        item["editorial_slot"], item["selection_reason"] = slot, f"protected:{cls}"
    while len(selected) < max_posts:
        candidates = [x for x in ranked if eligible(x)]
        if not candidates: break
        def fill_rank(item):
            source, ctype = str(item.get("source") or "unknown"), str(item.get("content_type") or "news").lower()
            return (1 if source_counts[source] == 0 else 0, 1 if type_counts[ctype] == 0 else 0, 1 if leader_name(item) else 0, 1 if is_interview(item) else 0, {"leader_interview": 8, "research_breakthrough": 5, "major_industry_news": 4, "future_signal": 3, "fallback": 1}.get(class_of(item), 1), _score(item))
        item = max(candidates, key=fill_rank); selected.append(item); selected_ids.add(id(item))
        source_counts[str(item.get("source") or "unknown")] += 1; type_counts[str(item.get("content_type") or "news").lower()] += 1
        item.setdefault("editorial_slot", "fallback"); item.setdefault("selection_reason", "ranked_diversity_fill")
    return selected
