"""Generic priority-person and high-value ideas detection for substantive radar signals."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.expert_registry import apply_expert_features

TOP_AI_VOICES={"elon musk","sam altman","demis hassabis","dario amodei","jensen huang","yann lecun","yoshua bengio","geoffrey hinton","andrew ng","eric schmidt","ilya sutskever","noam shazeer","fei-fei li","stuart russell","nick bostrom","yuval noah harari","mustafa suleyman","mark zuckerberg","satya nadella","lisa su"}
PERSON_ALIASES={"elon musk":("elon musk","musk"),"sam altman":("sam altman","altman","سم آلتمن","سم التمن"),"demis hassabis":("demis hassabis","hassabis"),"dario amodei":("dario amodei","amodei"),"jensen huang":("jensen huang","huang"),"yann lecun":("yann lecun","yann le cun","lecun"),"yoshua bengio":("yoshua bengio","bengio"),"geoffrey hinton":("geoffrey hinton","hinton"),"andrew ng":("andrew ng",),"eric schmidt":("eric schmidt","schmidt"),"ilya sutskever":("ilya sutskever","sutskever"),"noam shazeer":("noam shazeer","shazeer"),"fei-fei li":("fei-fei li","fei fei li","fei-fei","fei fei"),"stuart russell":("stuart russell","russell"),"nick bostrom":("nick bostrom","bostrom"),"yuval noah harari":("yuval noah harari","yuval harari","harari"),"mustafa suleyman":("mustafa suleyman","suleyman"),"mark zuckerberg":("mark zuckerberg","zuckerberg"),"satya nadella":("satya nadella","nadella"),"lisa su":("lisa su",)}
INTERVIEW_TYPES={"interview","podcast","talk","lecture","fireside","conversation","discussion","q&a"}
INTERVIEW_TERMS=("interview","podcast","fireside chat","conversation","q&a","keynote q&a","question and answer","speaks with","talks with","in conversation","sit-down","سخنرانی","مصاحبه","پادکست","گفتگو","گفت‌وگو","پرسش و پاسخ")
MAX_FIELD_CHARS={"title":1200,"summary":4000,"description":4000,"source":600,"content_type":200,"speakers":1200,"speaker":600,"watch_person":600,"leader":600,"key_quote":1600}
ROOT = Path(__file__).resolve().parents[1]
IDEAS_PATH = ROOT / "config" / "leader_watchlist.yaml"
_IDEA_CACHE: list[dict[str, object]] | None = None

_NAME_PATTERNS={canonical: tuple(re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.I) for alias in aliases if " " in alias or any(ord(c) > 127 for c in alias)) for canonical, aliases in PERSON_ALIASES.items()}
_SINGLE_NAME_PATTERNS={canonical: tuple(re.compile(rf"\b{re.escape(alias)}\b", re.I) for alias in aliases if " " not in alias and alias.isascii()) for canonical, aliases in PERSON_ALIASES.items()}
_INTERVIEW_TERM_RE=re.compile("|".join(re.escape(term) for term in INTERVIEW_TERMS), re.I)
_WORD_TERM_RE_CACHE: dict[str, re.Pattern[str]] = {}
_UNSAFE_IDEA_TERMS = {"phi", "iit", "bci"}
_MIND_CATEGORIES = {"mind_consciousness", "philosophy_of_mind", "cognitive_science"}
_AI_PERSON_GROUPS = {"featured_ai_leaders", "ai_builders", "technology_strategists_and_industry_thinkers"}
_MIND_PERSON_GROUPS = {"consciousness_and_mind_ai"}
_IDEA_SUBLANE_BY_NAME = {
    "consciousness": "ai_consciousness",
    "predictive_processing": "human_mind",
    "global_workspace": "human_mind",
    "integrated_information": "human_mind",
    "embodied_and_extended_mind": "human_mind",
    "philosophy_of_mind_and_ai": "philosophy_of_mind",
    "future_of_mind": "future_of_mind",
}


def _bounded(value: object, limit: int) -> str:
    return str(value or "")[:limit]

def _normalize(value: str) -> str:
    return value.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").replace("ـ", " ")

def _text(item):
    return _normalize(" ".join(_bounded(item.get(k), MAX_FIELD_CHARS[k]) for k in MAX_FIELD_CHARS).lower())

def _explicit_people(item):
    return {_normalize(str(item.get(k) or "").strip().lower()) for k in ("speaker","speakers","watch_person","leader","priority_person") if str(item.get(k) or "").strip()}

def _watchlist_person(item):
    if not (item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("protected_content")):
        return ""
    return _normalize(str(item.get("watch_person") or item.get("leader") or "").strip().lower())

def _interview_context(item):
    ctype = _normalize(str(item.get("content_type") or "").strip().lower())
    title = _normalize(_bounded(item.get("title"), MAX_FIELD_CHARS["title"]).lower())
    return ctype in INTERVIEW_TYPES or bool(_INTERVIEW_TERM_RE.search(title))

def matched_priority_people(item, *, text: str | None = None):
    text = _text(item) if text is None else _normalize(text)
    explicit = _explicit_people(item)
    matches = []
    watch_person = _watchlist_person(item)
    if watch_person:
        matches.append(watch_person)
    interview_context = _interview_context(item)
    for canonical, aliases in PERSON_ALIASES.items():
        if canonical in explicit or any(_normalize(a.lower()) in explicit for a in aliases):
            matches.append(canonical)
            continue
        if any(pattern.search(text) for pattern in _NAME_PATTERNS.get(canonical, ())):
            matches.append(canonical)
            continue
        if interview_context and any(pattern.search(text) for pattern in _SINGLE_NAME_PATTERNS.get(canonical, ())):
            matches.append(canonical)
    return sorted(set(matches))

def _load_ideas() -> list[dict[str, object]]:
    global _IDEA_CACHE
    if _IDEA_CACHE is not None:
        return _IDEA_CACHE
    try:
        payload = yaml.safe_load(IDEAS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        _IDEA_CACHE = []
        return _IDEA_CACHE
    raw = payload.get("ideas_and_theories", []) if isinstance(payload, dict) else []
    if isinstance(raw, dict):
        _IDEA_CACHE = [dict(value, name=str(key)) for key, value in raw.items() if isinstance(value, dict)]
    elif isinstance(raw, list):
        _IDEA_CACHE = [x for x in raw if isinstance(x, dict)]
    else:
        _IDEA_CACHE = []
    return _IDEA_CACHE

def _load_watchlist_people() -> list[dict[str, object]]:
    try:
        payload = yaml.safe_load(IDEAS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return []
    people = payload.get("people", {}) if isinstance(payload, dict) else {}
    rows: list[dict[str, object]] = []
    if isinstance(people, dict):
        for group, cfg in people.items():
            if not isinstance(cfg, dict):
                continue
            for name in cfg.get("names", []) or []:
                rows.append({"name": str(name), "group": str(group), "priority": cfg.get("priority", 0)})
    return rows

def _term_pattern(term: str) -> re.Pattern[str]:
    normalized = _normalize(term.strip().lower())
    cached = _WORD_TERM_RE_CACHE.get(normalized)
    if cached is not None:
        return cached
    parts = [re.escape(part) for part in normalized.split() if part]
    separator = r"\s+"
    expression = separator.join(parts)
    pattern = re.compile(rf"(?<!\w){expression}(?!\w)", re.I)
    _WORD_TERM_RE_CACHE[normalized] = pattern
    return pattern

def _idea_terms(idea: dict[str, object]) -> list[str]:
    terms: list[str] = []
    raw_terms = idea.get("ai_bridge_terms")
    if not isinstance(raw_terms, list):
        return terms
    for raw in raw_terms:
        term = str(raw).strip().lower()
        if not term or term in _UNSAFE_IDEA_TERMS:
            continue
        terms.append(term)
    return terms

def _idea_area(idea: dict[str, object]) -> str:
    return str(idea.get("mission_area") or "").strip().lower()

def _idea_sublane(idea: dict[str, object]) -> str:
    name = str(idea.get("name") or "").strip().lower()
    return _IDEA_SUBLANE_BY_NAME.get(name, "")

def _person_groups(people: list[str]) -> set[str]:
    normalized = {_normalize(x).strip().lower() for x in people}
    groups: set[str] = set()
    for row in _load_watchlist_people():
        if _normalize(str(row.get("name") or "")).strip().lower() in normalized:
            groups.add(str(row.get("group") or "").strip().lower())
    return groups

def _apply_directional_idea_metadata(item, ideas: list[str], matched_details: list[dict[str, object]]) -> None:
    areas = sorted({x for x in (_idea_area(d) for d in matched_details) if x})
    sublanes = sorted({x for x in (_idea_sublane(d) for d in matched_details) if x})
    item["priority_idea_areas"] = areas
    item["priority_idea_sublanes"] = sublanes
    matched_people = matched_priority_people(item)
    item["priority_idea_people"] = matched_people
    groups = _person_groups(matched_people)
    item["person_idea_direction"] = ""
    has_ai_person = bool(set(matched_people) & TOP_AI_VOICES) or bool(groups & _AI_PERSON_GROUPS)
    has_mind_person = bool(groups & _MIND_PERSON_GROUPS) or bool(str(item.get("person_category") or item.get("leader_category") or "").strip().lower() in _MIND_CATEGORIES)
    if ideas and matched_people:
        if has_ai_person and "mind_cognition" in areas:
            item["person_idea_direction"] = "ai_to_mind"
        elif has_mind_person and (any(area in {"ai_core", "convergence"} for area in areas) or "future_of_mind" in sublanes):
            item["person_idea_direction"] = "mind_to_ai"
        elif has_mind_person:
            item["person_idea_direction"] = "mind_to_mind"
        elif has_ai_person:
            item["person_idea_direction"] = "ai_to_ai"

def _match_priority_ideas(item, text: str) -> list[str]:
    matches: list[str] = []
    details: list[dict[str, object]] = []
    for idea in _load_ideas():
        terms = _idea_terms(idea)
        if not terms:
            continue
        if any(_term_pattern(term).search(text) for term in terms):
            matches.append(str(idea.get("name") or "").strip())
            details.append(idea)
    _apply_directional_idea_metadata(item, matches, details)
    return sorted(set(x for x in matches if x))

def _apply_idea_signal(item, text: str) -> list[str]:
    ideas = _match_priority_ideas(item, text)
    item["priority_ideas"] = ideas
    item["priority_idea_count"] = len(ideas)
    if ideas and not item.get("_priority_idea_signal_applied"):
        try:
            current = float(item.get("signal_score", 0) or 0)
        except (TypeError, ValueError):
            current = 0.0
        idea_bonus = min(6.0, 2.0 + 1.5 * max(0, len(ideas) - 1))
        item["priority_idea_bonus"] = idea_bonus
        item["signal_score"] = current + idea_bonus
        item["_priority_idea_signal_applied"] = True
    elif ideas:
        item.setdefault("priority_idea_bonus", min(6.0, 2.0 + 1.5 * max(0, len(ideas) - 1)))
    else:
        item.setdefault("priority_idea_bonus", 0.0)
    return ideas

def priority_people_features(item):
    if item.get("_publication_blocked"):
        return [], False, 0.0
    apply_expert_features(item)
    text = _text(item)
    _apply_idea_signal(item, text)
    people = matched_priority_people(item, text=text)
    if not people:
        return people, False, 0.0
    protected_ranked_story = bool(item.get("protected_content") and item.get("_rank_is_tier0"))
    is_substantive_interview = _interview_context(item) and len(text) >= 100
    is_tier0 = protected_ranked_story or is_substantive_interview
    return people, is_tier0, 50.0 if is_tier0 else 0.0

def is_substantive_priority_interview(item):
    return priority_people_features(item)[1]

def priority_people_bonus(item):
    return priority_people_features(item)[2]
