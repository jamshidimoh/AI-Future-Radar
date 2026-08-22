"""Generic tier-0 detection for substantive interviews and attributable quotes.

Tier-0 is an editorial classification, not a ranking side effect.  In
particular, an item must earn the classification from its own evidence; a
previously assigned ``tier0_rank`` must never make an item tier-0.
"""
from __future__ import annotations

import re

TOP_AI_VOICES={"elon musk","sam altman","demis hassabis","dario amodei","jensen huang","yann lecun","yoshua bengio","geoffrey hinton","andrew ng","eric schmidt","ilya sutskever","noam shazeer","fei-fei li","stuart russell","nick bostrom","yuval noah harari","mustafa suleyman","mark zuckerberg","satya nadella","lisa su"}
PERSON_ALIASES={"elon musk":("elon musk","musk"),"sam altman":("sam altman","altman"),"demis hassabis":("demis hassabis","hassabis"),"dario amodei":("dario amodei","amodei"),"jensen huang":("jensen huang","huang"),"yann lecun":("yann lecun","yann le cun","lecun"),"yoshua bengio":("yoshua bengio","bengio"),"geoffrey hinton":("geoffrey hinton","hinton"),"andrew ng":("andrew ng",),"eric schmidt":("eric schmidt","schmidt"),"ilya sutskever":("ilya sutskever","sutskever"),"noam shazeer":("noam shazeer","shazeer"),"fei-fei li":("fei-fei li","fei fei li","fei-fei","fei fei"),"stuart russell":("stuart russell","russell"),"nick bostrom":("nick bostrom","bostrom"),"yuval noah harari":("yuval noah harari","yuval harari","harari"),"mustafa suleyman":("mustafa suleyman","suleyman"),"mark zuckerberg":("mark zuckerberg","zuckerberg"),"satya nadella":("satya nadella","nadella"),"lisa su":("lisa su",)}
INTERVIEW_TYPES={"interview","podcast","talk","lecture","fireside","conversation","discussion","q&a"}
INTERVIEW_TERMS=("interview","podcast","fireside chat","conversation","q&a","keynote q&a","question and answer","speaks with","talks with","in conversation","sit-down","سخنرانی","مصاحبه","پادکست","گفتگو","گفت‌وگو","پرسش و پاسخ")
QUOTE_TERMS=("said","says","told","argued","warned","believes","predicts","stated","explained","می‌گوید","گفت","اظهار کرد","هشدار داد","معتقد است","پیش‌بینی کرد","توضیح داد")
MAX_FIELD_CHARS={"title":1200,"summary":4000,"description":4000,"source":600,"content_type":200,"speakers":1200,"speaker":600,"watch_person":600,"leader":600,"key_quote":1600}
_NAME_PATTERNS={canonical: tuple(re.compile(rf"\b{re.escape(alias)}\b", re.I) for alias in aliases) for canonical, aliases in PERSON_ALIASES.items() if any(" " in alias for alias in aliases)}
_SINGLE_NAME_PATTERNS={canonical: tuple(re.compile(rf"\b{re.escape(alias)}\b", re.I) for alias in aliases if " " not in alias) for canonical, aliases in PERSON_ALIASES.items()}
_INTERVIEW_TERM_RE=re.compile("|".join(re.escape(term) for term in INTERVIEW_TERMS), re.I)
_QUOTE_RE=re.compile("|".join(re.escape(term) for term in QUOTE_TERMS), re.I)
_NO_QUOTE_RE=re.compile(r"\b(no|without|not)\b.{0,35}\b(direct\s+)?(quote|quoted|attributable|statement)\b", re.I)

def _bounded(value: object, limit: int) -> str:
    return str(value or "")[:limit]

def _text(item):
    return " ".join(_bounded(item.get(k), MAX_FIELD_CHARS[k]) for k in MAX_FIELD_CHARS).lower()

def _explicit_people(item):
    return {str(item.get(k) or "").strip().lower() for k in ("speaker","speakers","watch_person","leader","priority_person") if str(item.get(k) or "").strip()}

def matched_priority_people(item, *, text: str | None = None):
    text = _text(item) if text is None else text
    explicit = _explicit_people(item)
    matches = []
    for canonical, aliases in PERSON_ALIASES.items():
        if canonical in explicit or any(a in explicit for a in aliases):
            matches.append(canonical)
            continue
        if any(pattern.search(text) for pattern in _NAME_PATTERNS.get(canonical, ())):
            matches.append(canonical)
            continue
        if any(pattern.search(text) for pattern in _SINGLE_NAME_PATTERNS.get(canonical, ())):
            ctype = str(item.get("content_type") or "").lower()
            title = _bounded(item.get("title"), MAX_FIELD_CHARS["title"]).lower()
            if ctype in INTERVIEW_TYPES or _INTERVIEW_TERM_RE.search(title):
                matches.append(canonical)
    return sorted(set(matches))

def _has_attributable_quote(item,text,people):
    if _NO_QUOTE_RE.search(text):
        return False
    quote = _bounded(item.get("key_quote"), MAX_FIELD_CHARS["key_quote"]).strip()
    if len(quote) >= 20:
        return True
    names=[a for p in people for a in PERSON_ALIASES.get(p,(p,))]
    if not names:
        return False
    left="(?:"+"|".join(re.escape(x) for x in names)+")\W{0,80}(?:"+_QUOTE_RE.pattern+")"
    right="(?:"+_QUOTE_RE.pattern+")\W{0,80}(?:"+"|".join(re.escape(x) for x in names)+")"
    return bool(re.search(left,text,re.I) or re.search(right,text,re.I))

def priority_people_features(item):
    text = _text(item)
    people = matched_priority_people(item, text=text)
    if not people:
        return people, False, 0.0
    ctype = str(item.get("content_type") or "").lower()
    title = _bounded(item.get("title"), MAX_FIELD_CHARS["title"]).lower()
    explicit_interview = ctype in INTERVIEW_TYPES or bool(_INTERVIEW_TERM_RE.search(title))
    if explicit_interview:
        is_tier0 = len(text) >= 100
    else:
        is_tier0 = _has_attributable_quote(item, text, people) and len(text) >= 280
    return people, is_tier0, 50.0 if is_tier0 else 0.0

def is_substantive_priority_interview(item):
    return priority_people_features(item)[1]

def priority_people_bonus(item):
    return priority_people_features(item)[2]
