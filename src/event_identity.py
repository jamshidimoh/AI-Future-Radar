"""Hybrid event identity matcher used by the publication dedup gate."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

ALIASES = {
    "meta": ("meta", "متا"), "mark_zuckerberg": ("mark zuckerberg", "zuckerberg", "مارک زاکربرگ", "زاکربرگ"),
    "muse": ("muse", "میوز"), "personal_superintelligence": ("personal superintelligence", "personal super intelligence", "سوپر هوش شخصی"),
    "terence_tao": ("terence tao", "tao", "ترنس تائو"),
    "stanford_hai": ("stanford hai", "stanford institute for human-centered artificial intelligence", "استنفورد hai", "stanford"),
    "openai": ("openai", "اوپن ای آی", "اوپنای"), "anthropic": ("anthropic", "انتروپیک"),
    "google": ("google", "گوگل"), "nvidia": ("nvidia", "انویدیا"),
    "chatgpt_images": ("chatgpt images", "chatgpt images 2.5"),
}
EVENTS = {
    "launch": ("launch", "launched", "launches", "introduce", "introduced", "introduces", "unveil", "unveiled", "معرفی", "رونمایی", "عرضه"),
    "announcement": ("announce", "announced", "announcement", "اعلام", "اعلام کرد", "اعلامیه"),
    "warning": ("warning", "warn", "warns", "هشدار", "نگرانی"),
    "research": ("research", "study", "paper", "findings", "پژوهش", "مطالعه", "یافته", "تحقیق"),
    "legal_review": ("legal", "law", "laws", "legal review", "rights", "قانونی", "قوانین", "بررسی حقوقی"),
    "funding": ("funding", "grant", "investment", "سرمایه", "کمک مالی", "گرنت"),
    "security": ("security", "breach", "incident", "vulnerability", "hack", "نفوذ", "نقض امنیتی", "آسیب پذیری", "آسیب‌پذیری"),
    "benchmark": ("benchmark", "evaluation", "ارزیابی", "بنچمارک"),
}
STOP = {"the","a","an","of","in","on","for","to","and","or","is","are","with","from","by","new","latest","news","update","this","that","how","what","why","about","در","به","از","با","و","یا","برای","این","آن","که","را","یک","است","شد","می","های","ها","خبر","جدید"}
MATERIAL = {"finding","findings","evidence","cause","impact","scope","scale","timeline","postmortem","newly","revealed","discovered","discovery","details","جزئیات","یافته","شواهد","علت","دامنه","مقیاس","کشف","تأیید","تایید","confirmed","confirmation","vulnerability","آسیب پذیری","آسیب‌پذیری","severity","شدت","damage","خسارت","mitigation","رفع","remediation"}

def normalize(text: Any) -> str:
    s = str(text or "").lower().replace("ي","ی").replace("ك","ک").replace("‌"," ")
    s = re.sub(r"https?://\S+", " ", s)
    for canonical, aliases in sorted(ALIASES.items(), key=lambda x:max(map(len,x[1])), reverse=True):
        for alias in sorted(aliases, key=len, reverse=True):
            s = re.sub(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", canonical, s)
    s = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9_]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def tokens(text: Any) -> set[str]: return {t for t in re.findall(r"[a-zA-Z\u0600-\u06FF0-9_]+", normalize(text)) if len(t)>2 and t not in STOP}
def entities(text: Any) -> set[str]:
    s=normalize(text); return {k for k in ALIASES if re.search(r"(?<![\w])"+re.escape(k)+r"(?![\w])",s)}
def events(text: Any) -> set[str]:
    s=normalize(text); return {k for k,v in EVENTS.items() if any(re.search(r"(?<![\w])"+re.escape(a)+r"(?![\w])",s) for a in v)}
def material(text: Any) -> set[str]: return tokens(text) & {normalize(x) for x in MATERIAL}
def jac(a:set[str],b:set[str])->float: return len(a&b)/len(a|b) if a and b else 0.0

def _time(value: Any):
    if not value: return None
    try:
        d=datetime.fromisoformat(str(value).replace("Z","+00:00")); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError: return None

@lru_cache(maxsize=8192)
def _event_features_cached(title, summary, description, content, event_time, published, published_at):
    text=" ".join(str(x or "") for x in (title, summary, description, content))
    return {"entities":entities(text),"events":events(text),"tokens":tokens(text),"material":material(text),"title":normalize(title or ""),"time":_time(event_time or published or published_at),"norm":normalize(text)}

def event_features(item: dict[str,Any])->dict[str,Any]:
    return _event_features_cached(
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("description") or ""),
        str(item.get("content") or ""),
        str(item.get("event_time") or ""),
        str(item.get("published") or ""),
        str(item.get("published_at") or ""),
    )

def has_material_update(a:dict[str,Any],b:dict[str,Any])->bool:
    fa,fb=event_features(a),event_features(b)
    na=set(re.findall(r"\b\d+(?:\.\d+)?\b",fa["norm"])); nb=set(re.findall(r"\b\d+(?:\.\d+)?\b",fb["norm"]))
    if na and nb and na != nb: return True
    return len(fa["material"] - fb["material"]) >= 2 or len(fb["material"] - fa["material"]) >= 2

def compare_events(a:dict[str,Any],b:dict[str,Any])->tuple[str,float,dict[str,Any]]:
    fa,fb=event_features(a),event_features(b); shared=fa["entities"]&fb["entities"]; shared_events=fa["events"]&fb["events"]
    context=jac(fa["tokens"],fb["tokens"]); title=SequenceMatcher(None,fa["title"],fb["title"]).ratio() if fa["title"] and fb["title"] else 0.0
    strong_product=bool(shared&{"muse","chatgpt_images"}); strong_person=bool(shared&{"mark_zuckerberg","terence_tao"}); strong_source=bool(shared&{"stanford_hai"})
    same=((strong_product and bool(shared_events)) or (strong_product and context>=0.55 and title>=0.65) or (strong_person and bool(shared_events) and context>=0.18) or (strong_source and context>=0.35) or (bool(shared_events) and context>=0.65) or (len(shared)>=2 and bool(shared_events) and context>=0.20) or (title>=0.90 and context>=0.45))
    material_update=has_material_update(a,b)
    score=min(1.0,0.30*min(1.0,len(shared)/2.0)+0.20*bool(shared_events)+0.30*context+0.20*title+(0.18 if strong_product else 0))
    evidence={"shared_entities":sorted(shared),"shared_events":sorted(shared_events),"context_jaccard":round(context,4),"title_similarity":round(title,4),"material_update":material_update}
    if same and material_update: return "UPDATE",score,evidence
    if same: return "DUPLICATE",score,evidence
    if shared and (shared_events or context>=0.16): return "RELATED",score,evidence
    return "NEW",score,evidence

def is_duplicate(candidate:dict[str,Any],history:list[dict[str,Any]])->bool: return any(compare_events(candidate,p)[0]=="DUPLICATE" for p in history)
