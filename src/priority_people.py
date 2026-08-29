"""Generic priority-person detection for substantive interviews and protected leader activity."""
from __future__ import annotations

import re

TOP_AI_VOICES={"elon musk","sam altman","demis hassabis","dario amodei","jensen huang","yann lecun","yoshua bengio","geoffrey hinton","andrew ng","eric schmidt","ilya sutskever","noam shazeer","fei-fei li","stuart russell","nick bostrom","yuval noah harari","mustafa suleyman","mark zuckerberg","satya nadella","lisa su"}
PERSON_ALIASES={"elon musk":("elon musk","musk"),"sam altman":("sam altman","altman","سم آلتمن","سم التمن"),"demis hassabis":("demis hassabis","hassabis"),"dario amodei":("dario amodei","amodei"),"jensen huang":("jensen huang","huang"),"yann lecun":("yann lecun","yann le cun","lecun"),"yoshua bengio":("yoshua bengio","bengio"),"geoffrey hinton":("geoffrey hinton","hinton"),"andrew ng":("andrew ng",),"eric schmidt":("eric schmidt","schmidt"),"ilya sutskever":("ilya sutskever","sutskever"),"noam shazeer":("noam shazeer","shazeer"),"fei-fei li":("fei-fei li","fei fei li","fei-fei","fei fei"),"stuart russell":("stuart russell","russell"),"nick bostrom":("nick bostrom","bostrom"),"yuval noah harari":("yuval noah harari","yuval harari","harari"),"mustafa suleyman":("mustafa suleyman","suleyman"),"mark zuckerberg":("mark zuckerberg","zuckerberg"),"satya nadella":("satya nadella","nadella"),"lisa su":("lisa su",)}
INTERVIEW_TYPES={"interview","podcast","talk","lecture","fireside","conversation","discussion","q&a"}
INTERVIEW_TERMS=("interview","podcast","fireside chat","conversation","q&a","keynote q&a","question and answer","speaks with","talks with","in conversation","sit-down","سخنرانی","مصاحبه","پادکست","گفتگو","گفت‌وگو","پرسش و پاسخ")
MAX_FIELD_CHARS={"title":1200,"summary":4000,"description":4000,"source":600,"content_type":200,"speakers":1200,"speaker":600,"watch_person":600,"leader":600,"key_quote":1600}

_NAME_PATTERNS={canonical: tuple(re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.I) for alias in aliases if " " in alias or any(ord(c) > 127 for c in alias)) for canonical, aliases in PERSON_ALIASES.items()}
_SINGLE_NAME_PATTERNS={canonical: tuple(re.compile(rf"\b{re.escape(alias)}\b", re.I) for alias in aliases if " " not in alias and alias.isascii()) for canonical, aliases in PERSON_ALIASES.items()}
_INTERVIEW_TERM_RE=re.compile("|".join(re.escape(term) for term in INTERVIEW_TERMS), re.I)

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

def priority_people_features(item):
    if item.get("_publication_blocked"):
        return [], False, 0.0
    text = _text(item)
    people = matched_priority_people(item, text=text)
    if not people:
        return people, False, 0.0
    protected_ranked_story = bool(item.get("protected_content") and item.get("_rank_is_tier0"))
    is_tier0 = protected_ranked_story or (_interview_context(item) and len(text) >= 100)
    return people, is_tier0, 50.0 if is_tier0 else 0.0

def is_substantive_priority_interview(item):
    return priority_people_features(item)[1]

def priority_people_bonus(item):
    return priority_people_features(item)[2]
