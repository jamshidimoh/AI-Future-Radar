"""Canonical evidence-first editorial engine for AI Future Radar."""
from __future__ import annotations
import re,time
from collections import Counter
AI={"artificial intelligence","ai","machine learning","deep learning","large language model","llm","foundation model","generative ai","agentic ai","ai agent","agents","agi","superintelligence","reasoning model","multimodal","vision-language model","vlm","computer vision","copilot","ai coding","llm inference","llm training","world model","synthetic data","ai safety","ai alignment","ai governance","ai policy","ai for science","ai research","ai benchmark","physical ai","embodied ai","computer use","robotics"}
Q={"quantum computing","quantum computer","quantum processor","quantum chip","quantum algorithm","quantum machine learning","quantum ai","quantum neural network","quantum optimization","quantum simulation","quantum error correction","qpu","qubit"}
QAI=(Q-{"quantum optimization","qubit"})|{"ai","artificial intelligence","machine learning","llm","agi","hybrid quantum-classical","quantum inference"}
M={"consciousness","machine consciousness","ai consciousness","sentience","qualia","self-awareness","awareness","cognitive science","cognition","cognitive","neuroscience","computational neuroscience","predictive processing","active inference","global workspace","integrated information","philosophy of mind","brain modeling","neural computation","memory","attention"}
MB={"ai","artificial intelligence","machine learning","computational","neural computation","brain-computer interface","bci","neurotechnology","brain decoding","neural recording","brain stimulation","artificial neural network","llm","agi","robotics","simulation","cognitive computing"}
F={"future","forecast","outlook","futurism","futurist","foresight","longtermism","singularity","future studies","technology forecasting","civilization futures","future of technology","future of intelligence","human enhancement","transhumanism","existential risk"}
FB={"ai","artificial intelligence","machine learning","agi","robotics","physical ai","quantum computing","bci","neurotechnology","synthetic biology","computational biology","autonomous science","ai chip","gpu","npu","tpu","photonic computing","neuromorphic","space technology","advanced materials","nanotechnology","biotechnology","longevity","humanoid robots"}
BIO={"ai drug discovery","ai biology","protein design ai","digital biology","computational biology","synthetic biology","biological computing"}
ROB={"humanoid robot","robot foundation model","vision-language-action","physical ai","embodied intelligence","autonomous robot","robot learning"}
BCI={"brain-computer interface","bci","neural interface","neurotechnology","brain decoding","neural recording","brain stimulation","neuralink"}
COMP={"ai chip","gpu","tpu","npu","ai accelerator","neuromorphic computing","edge ai","ai data center","photonic computing","optical computing","memory computing","energy-efficient ai"}
NEWS={"launch","released","release","announced","announce","funding","regulation","policy","partnership","investment","breakthrough","new model","product launch","benchmark result","deployment"}
RES={"paper","research","study","preprint","scientific","experiment","findings","method","benchmark","peer reviewed","journal article"}
INT={"interview","conversation","fireside","keynote","podcast","discussion","q&a","talk with","speaks with","in conversation","sits down with"}
LOW={"unboxing","giveaway","merch","sponsor","product review","prank","reaction video"}
NEGATED_AI_PATTERNS=(r"\bno\s+(?:direct\s+)?(?:link|connection|relation|evidence)\s+to\s+ai\b",r"\bno\s+ai\s+(?:link|connection|relation|evidence)\b",r"\bwithout\s+(?:any\s+)?ai\b",r"\bnot\s+(?:related|connected)\s+to\s+ai\b",r"\bno\s+connection\s+with\s+ai\b")
def _text(x): return " ".join(str(x.get(k) or "") for k in ("title","summary","description")).lower()
def _has(t,terms):
    for z in terms:
        term=z.lower()
        if term=="ai":
            if any(re.search(p,t,re.I) for p in NEGATED_AI_PATTERNS): continue
            if re.search(r"\bai\b",t,re.I): return True
            continue
        if term=="agi":
            if re.search(r"\bagi\b",t,re.I): return True
            continue
        if len(term)<=3 and term.isalpha():
            if re.search(rf"\b{re.escape(term)}\b",t,re.I): return True
            continue
        if term in t:return True
    return False
def _hits(t,terms):
    out=[]
    for z in terms:
        term=z.lower()
        if term=="ai":
            if any(re.search(p,t,re.I) for p in NEGATED_AI_PATTERNS):continue
            if re.search(r"\bai\b",t,re.I):out.append(z)
        elif term=="agi":
            if re.search(r"\bagi\b",t,re.I):out.append(z)
        elif len(term)<=3 and term.isalpha():
            if re.search(rf"\b{re.escape(term)}\b",t,re.I):out.append(z)
        elif term in t:out.append(z)
    return sorted(set(out))
def _topic(t,extra=None):
    e={str(z).lower() for z in (extra or [])}
    if _has(t,Q):return ("quantum_ai",_hits(t,Q|QAI)[:6]) if _has(t,QAI) else ("out_of_scope",[])
    if _has(t,M):return ("consciousness_cognition",_hits(t,M|MB)[:6]) if _has(t,MB) else ("out_of_scope",[])
    if _has(t,F):return ("future_technology",_hits(t,F|FB)[:6]) if _has(t,FB) else ("out_of_scope",[])
    if _has(t,BIO):return ("bio_ai",_hits(t,BIO)[:6]) if _has(t,AI|{"machine learning","computational"}) else ("out_of_scope",[])
    if _has(t,BCI):return ("bci_neuro_ai",_hits(t,BCI)[:6]) if _has(t,AI|{"computational","neural"}) else ("out_of_scope",[])
    if _has(t,ROB):return ("robotics_embodied",_hits(t,ROB)[:6]) if _has(t,AI|{"autonomous","learning"}) else ("out_of_scope",[])
    if _has(t,COMP):return ("computing_infrastructure",_hits(t,COMP)[:6]) if _has(t,AI|{"inference","training","accelerator"}) else ("out_of_scope",[])
    return ("ai_core",_hits(t,AI|e)[:6]) if _has(t,AI|e) else ("out_of_scope",[])
def filter_ai_relevance(items,ai_keywords=None):
    out=[];drop=0;reason={"ai_core":"ai_evidence","quantum_ai":"quantum_ai_bridge","consciousness_cognition":"mind_technology_bridge","future_technology":"future_technology_bridge","bio_ai":"bio_ai_bridge","bci_neuro_ai":"bci_ai_bridge","robotics_embodied":"robotics_ai_bridge","computing_infrastructure":"computing_ai_bridge"}
    for raw in items:
        x=dict(raw);t=_text(x)
        if _has(t,LOW):continue
        category=str(x.get("category") or "").strip().lower()
        source_type=str(x.get("source_type") or "").strip().lower()
        metadata_ai = category == "ai" and source_type != "global_forum"
        if metadata_ai:
            fam,ev="ai_core",["explicit_ai_metadata"]
        else:
            fam,ev=_topic(t,ai_keywords)
        if fam=="out_of_scope":drop+=1;continue
        x.update(_ai_link=True,relevance_reason=reason[fam],relevance_evidence=ev,topic_family=fam,evidence_level="A");out.append(x)
    print(f"[AI Gate] rejected={drop} | kept={len(out)}")
    return out
def _age(p):
    if not p:return None
    try:return max(0,(time.time()-time.mktime(time.strptime(p,"%Y-%m-%d %H:%M")))/3600)
    except:return None
def _leader(x,prior):
    v=str(x.get("watch_person") or x.get("leader") or "").strip()
    if v:return v
    t=_text(x)
    for n in sorted(prior or {},key=len,reverse=True):
        if n.lower() in t:return n
    return ""
def _is_interview(x):return str(x.get("content_type") or "").lower() in {"interview","podcast","talk","lecture","fireside","conversation","discussion","q&a"} or bool(x.get("interview_signal")) or _has(_text(x),INT)
def _is_research(x):return str(x.get("content_type") or "").lower() in {"research","paper","study","preprint"} or bool(x.get("research_signal")) or _has(_text(x),RES)
def _is_news(x):return str(x.get("content_type") or "").lower() in {"news","official","product_news"} or bool(x.get("is_trending_query")) or _has(_text(x),NEWS)
def _is_trend(x):return str(x.get("topic_family") or "") in {"future_technology","consciousness_cognition","quantum_ai"}
def classify_editorial_item(x,prior=None):
    fam=str(x.get("topic_family") or _topic(_text(x))[0]);lead=_leader(x,prior or {});ls=bool(lead and (x.get("is_leader_watch") or x.get("leader_watch_protected")));iv=_is_interview(x);rs=_is_research(x);nw=_is_news(x);tr=_is_trend(x)
    if lead and iv and (x.get("is_leader_watch") or x.get("leader_watch_protected")):cls,conf="leader_interview",1
    elif x.get("is_leader_watch") and not lead:cls,conf="fallback",.35
    elif fam in {"quantum_ai","consciousness_cognition","future_technology","bio_ai","bci_neuro_ai","robotics_embodied","computing_infrastructure"}:cls,conf="convergence_signal",.92
    elif rs:cls,conf="research_breakthrough",.9
    elif nw and not iv:cls,conf="major_industry_news",.86
    elif fam=="ai_core" and not iv:cls,conf="ai_signal",.82
    else:cls,conf="fallback",.35
    return {"leader":lead,"leader_signal":ls,"interview_signal":iv,"research_signal":rs,"news_signal":nw,"trend_signal":tr,"topic_family":fam,"editorial_class":cls,"editorial_confidence":conf,"classification_evidence":[]}
def rs_or_news(c):return bool(c.get("research_signal") or c.get("news_signal"))
def enrich_items(items,leader_priorities,source_history=None,policy=None):
    policy=policy or {};out=[]
    for raw in items:
        x=dict(raw);c=classify_editorial_item(x,leader_priorities);age=_age(str(x.get("published") or ""));fresh=10 if age is not None and age<=24 else 8 if age is not None and age<=48 else 6 if age is not None and age<=72 else 4 if age is not None and age<=168 else 1;tier=int(x.get("source_tier") or 3);cred={1:9,2:7,3:5}.get(tier,4)+(1 if c["research_signal"] else 0);impact={"ai_core":7,"quantum_ai":8,"consciousness_cognition":8,"future_technology":8,"robotics_embodied":8,"bio_ai":8,"bci_neuro_ai":8,"computing_infrastructure":8}.get(c["topic_family"],3);future=10 if c["topic_family"]!="ai_core" else 7;conv=10 if c["editorial_class"]=="convergence_signal" else 4;novel=10 if _has(_text(x),{"breakthrough","new model","first","sota"}) else 7 if rs_or_news(c) else 4;hype=7 if str(x.get("content_type") or "").lower()=="community" else 2;score=10*(impact*.2+min(10,cred)*.3+future*.15+novel*.1+fresh*.1+conv*.1-hype*.05)
        if c["leader_signal"]:score+=int(policy.get("leader_priority_weight",2))*int((leader_priorities or {}).get(c["leader"],0))
        x.update(c,ai_relevant=bool(x.get("_ai_link")),freshness_hours=age,impact_score=impact,scientific_credibility=min(10,cred),technological_readiness=7,novelty_score=novel,future_relevance=future,cross_domain_convergence=conv,hype_risk=hype,priority_score=round(score,2),editorial_score=round(score,2));out.append(x)
    return out
def contract_summary(items):return {"count":len(items),"leaders":sum(bool(x.get("leader") or x.get("watch_person")) for x in items),"interviews":sum(_is_interview(x) for x in items),"news":sum(_is_news(x) for x in items),"trends":sum(_is_trend(x) for x in items),"research":sum(_is_research(x) for x in items),"sources":len({str(x.get("source") or "unknown") for x in items}),"classes":dict(Counter(str(x.get("editorial_class") or "fallback") for x in items)),"topic_families":dict(Counter(str(x.get("topic_family") or "unknown") for x in items))}
def filter_low_signal(items):return [x for x in items if not _has(_text(x),LOW)]
