"""Dependency-free event identity for cross-source news deduplication."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any

STOPWORDS={"the","a","an","and","or","of","in","on","for","to","with","by","at","as","is","are","was","were","be","been","this","that","new","latest","news","update","says","said","will","has","have","from","into","about","after","در","به","از","با","و","یا","برای","که","این","آن","یک","های","ها","است","شد","می","را","بر","هم","نیز","درباره","توسط","کرد","کند"}
ALIASES={
 "meta":"meta","متا":"meta","facebook":"meta","mark zuckerberg":"mark_zuckerberg","مارک زاکربرگ":"mark_zuckerberg","زاکربرگ":"mark_zuckerberg",
 "muse":"muse","personal superintelligence":"personal_superintelligence","سوپر هوش شخصی":"personal_superintelligence","ai agent":"ai_agent","ai agents":"ai_agent","عامل هوش مصنوعی":"ai_agent","عامل هوشمند":"ai_agent",
 "terence tao":"terence_tao","ترنس تائو":"terence_tao","تِرنس تائو":"terence_tao","تائو":"terence_tao","open problems":"open_problems","open problem":"open_problems","مسائل باز":"open_problems","مسئله باز":"open_problems","open science":"open_science","علم باز":"open_science",
 "stanford hai":"stanford_hai","stanford human-centered ai":"stanford_hai","استنفورد":"stanford_hai","local laws":"local_laws","local law":"local_laws","قوانین محلی":"local_laws","قانون محلی":"local_laws","discriminatory":"discriminatory","تبعیض آمیز":"discriminatory","تبعیض‌آمیز":"discriminatory","تبعیض":"discriminatory","legal review":"legal_review","legal analysis":"legal_review","بررسی حقوقی":"legal_review","تحلیل حقوقی":"legal_review",
 "introduce":"introduce","introduced":"introduce","introducing":"introduce","معرفی":"introduce","رونمایی":"introduce","launch":"launch","launched":"launch","launches":"launch","عرضه":"launch","راه اندازی":"launch","راه‌اندازی":"launch","announce":"announce","announced":"announce","announcement":"announce","اعلام":"announce","warning":"warning","warns":"warning","warn":"warning","هشدار":"warning","study":"study","report":"report","بررسی":"study","گزارش":"report","research":"research","پژوهش":"research","agent":"ai_agent",
 "security vulnerability":"security_vulnerability","security flaw":"security_vulnerability","آسیب پذیری امنیتی":"security_vulnerability","آسیب‌پذیری امنیتی":"security_vulnerability","benchmark":"benchmark","بنچمارک":"benchmark","performance":"performance","عملکرد":"performance","result":"result","results":"result","نتایج":"result"
}
EVENT_TYPES={"introduce","launch","announce","warning","study","report","research","funding","acquisition","partnership","appointment","security_vulnerability","benchmark","result"}
MATERIAL={"finding","findings","evidence","cause","impact","scope","scale","timeline","postmortem","transcript","details","detail","mechanism","technical","forensic","newly","revealed","discovered","vulnerability","vulnerabilities","mitigation","remediation","confirmed","confirmation","severity","damage","affected","victims","attackers","exploit","exploited","benchmark","results","performance","یافته","یافته‌ها","شواهد","علت","اثر","دامنه","مقیاس","جزئیات","مکانیسم","فنی","تأیید","تایید","آسیب‌پذیری","آسیب پذیری","رفع","شدت","خسارت","بنچمارک","نتایج","عملکرد"}
ORG={"meta","openai","google","microsoft","anthropic","nvidia","stanford_hai"}
PEOPLE={"mark_zuckerberg","terence_tao"}
PRODUCTS={"muse","gpt","claude","gemini","qwen","llama"}
CONCEPTS={"personal_superintelligence","ai_agent","open_problems","open_science","local_laws","discriminatory","legal_review"}

def normalize(text:Any)->str:
    v=str(text or "").lower().replace("ي","ی").replace("ك","ک").replace("‌"," ")
    for source,target in sorted(ALIASES.items(),key=lambda x:len(x[0]),reverse=True): v=re.sub(r"(?<![\w])+"+re.escape(source)+r"(?![\w])",target,v)
    v=re.sub(r"https?://\S+"," ",v); v=re.sub(r"[^a-zA-Z\u0600-\u06FF0-9_]+"," ",v)
    return re.sub(r"\s+"," ",v).strip()

def tokens(text:Any)->set[str]: return {t for t in re.findall(r"[a-zA-Z\u0600-\u06FF0-9_]+",normalize(text)) if t not in STOPWORDS and len(t)>2}

def _set(rep,key): return set(rep.get(key) or [])

def _j(a,b): return len(a&b)/len(a|b) if a and b else 0.0

def _parse_dt(v):
    try:
        if not v:return None
        d=datetime.fromisoformat(str(v).replace("Z","+00:00")); return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except ValueError:return None

def event_representation(item:dict[str,Any])->dict[str,Any]:
    text=" ".join(str(item.get(k) or "") for k in ("title","summary","description","why_it_matters","content")); norm=normalize(text); ts=tokens(norm)
    return {"organizations":sorted(ts&ORG),"people":sorted(ts&PEOPLE),"products":sorted(ts&PRODUCTS),"concepts":sorted(ts&CONCEPTS),"event_types":sorted(ts&EVENT_TYPES),"material":sorted(ts&MATERIAL),"numbers":sorted(set(re.findall(r"\b\d+(?:\.\d+)?\b",norm))),"tokens":sorted(ts),"event_time":item.get("event_time") or item.get("published") or item.get("pub_date") or item.get("published_at") or ""}

def same_event_identity(a,b)->bool:
    if _set(a,"people")&_set(b,"people") and _set(a,"products")&_set(b,"products") and (_set(a,"event_types")&_set(b,"event_types") or _set(a,"concepts")&_set(b,"concepts")): return True
    if _set(a,"organizations")&_set(b,"organizations") and _set(a,"people")&_set(b,"people") and _set(a,"products")&_set(b,"products"): return True
    if _set(a,"organizations")&_set(b,"organizations") and len(_set(a,"concepts")&_set(b,"concepts"))>=2 and _set(a,"event_types")&_set(b,"event_types"): return True
    if len(_set(a,"concepts")&_set(b,"concepts"))>=2 and _set(a,"event_types")&_set(b,"event_types"): return True
    return False

def material_update(a,b)->bool:
    na,nb=_set(a,"numbers"),_set(b,"numbers")
    if na and nb and na!=nb:return True
    ma,mb=_set(a,"material"),_set(b,"material")
    if len(ma-mb)>=2 or len(mb-ma)>=2:return True
    ea,eb=_set(a,"event_types"),_set(b,"event_types")
    return bool(ea and eb and ea!=eb)

def event_similarity(item,prior)->float:
    a,b=event_representation(item),event_representation(prior); score=sum(_j(_set(a,k),_set(b,k))*w for k,w in (("organizations",.16),("people",.18),("products",.17),("concepts",.24),("event_types",.10),("tokens",.15)))
    if same_event_identity(a,b): score=max(score,.78)
    da,db=_parse_dt(a.get("event_time")),_parse_dt(b.get("event_time"))
    if da and db:
        hours=abs((da-db).total_seconds())/3600
        score += .08 if hours<=48 else (.04 if hours<=168 else (-.08 if hours>720 else 0))
    return max(0,min(1,round(score,4)))

def classify_story(candidate,prior):
    a,b=event_representation(candidate),event_representation(prior); score=event_similarity(candidate,prior); same=same_event_identity(a,b); update=material_update(a,b)
    if same and update:return "UPDATE",score
    if same:return "DUPLICATE",score
    if score>=.80 and not update:return "DUPLICATE",score
    if score>=.60 and update:return "UPDATE",score
    if score>=.52:return "RELATED",score
    return "NEW",score
