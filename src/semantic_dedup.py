"""تشخیص تکرار مفهومی/موضوعی در سطح Story، بین منابع و اجراها."""
import difflib
import json
import re
from dataclasses import dataclass

SEMANTIC_MARKER = "__semantic_story__:"
_STOPWORDS = {"در", "به", "از", "با", "را", "که", "این", "آن", "و", "یا", "برای", "تا", "بر", "هم", "نیز", "یک", "بی", "چه", "چون", "اگر", "ولی", "اما", "می", "شود", "است", "های", "ها", "کرد", "شد", "دارد", "کند", "خود", "هایش", "روی", "درباره", "پس", "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are", "with", "new", "how", "what", "why", "this", "that", "it", "its", "by", "at", "as", "be", "will", "can", "has", "have", "into", "over", "after", "says", "said", "latest", "update", "news", "podcast", "episode", "interview", "talk", "video"}
_ALIASES = {"nvidia": "nvidia", "انویدیا": "nvidia", "openai": "openai", "اوپن ای آی": "openai", "اوپنای": "openai", "google": "google", "گوگل": "google", "microsoft": "microsoft", "مایکروسافت": "microsoft", "meta": "meta", "amazon": "amazon", "آمازون": "amazon", "apple": "apple", "اپل": "apple", "anthropic": "anthropic", "انتروپیک": "anthropic", "x ai": "x_ai", "x.ai": "x_ai", "andrew ng": "andrew_ng", "اندرو نگ": "andrew_ng", "sam altman": "sam_altman", "سم آلتمن": "sam_altman", "elon musk": "elon_musk", "ایلان ماسک": "elon_musk", "ilya sutskever": "ilya_sutskever", "ایلیا سوتسکیور": "ilya_sutskever", "anil seth": "anil_seth", "آنیل ست": "anil_seth", "آنیل سث": "anil_seth", "demis hassabis": "demis_hassabis", "دیمیس هاسابیس": "demis_hassabis", "jensen huang": "jensen_huang", "جنسن هوانگ": "jensen_huang", "dario amodei": "dario_amodei", "داریو آمودی": "dario_amodei", "mit csail": "mit_csail", "mit": "mit", "building 32": "building_32", "building 23": "building_23", "deepmind": "deepmind", "google deepmind": "google_deepmind", "deep learning ai": "deeplearning_ai", "deeplearning.ai": "deeplearning_ai", "safe superintelligence": "ssi", "سوپرهوش ایمن": "ssi", "artificial general intelligence": "agi", "هوش عمومی مصنوعی": "agi", "superintelligence": "superintelligence", "سوپرهوش": "superintelligence", "consciousness": "consciousness", "آگاهی": "consciousness", "scaling laws": "scaling_laws", "قوانین مقیاس پذیری": "scaling_laws", "قوانین مقیاس‌پذیری": "scaling_laws", "ai agents": "ai_agents", "ai agent": "ai_agents", "عامل هوش مصنوعی": "ai_agents", "robotics": "robotics", "رباتیک": "robotics", "large language model": "llm", "large language models": "llm", "مدل زبانی بزرگ": "llm", "steps down": "departure_event", "step down": "departure_event", "stepped down": "departure_event", "leaving": "departure_event", "leaves": "departure_event", "left": "departure_event", "leave": "departure_event", "exodus": "departure_event", "departure": "departure_event", "depart": "departure_event", "losing": "departure_event", "resigns": "departure_event", "resigned": "departure_event", "resign": "departure_event", "خروج": "departure_event", "کناره گیری": "departure_event", "کناره‌گیری": "departure_event", "ترک": "departure_event", "استعفا": "departure_event"}
_ANCHOR_SET = {"nvidia", "openai", "google", "microsoft", "meta", "amazon", "apple", "anthropic", "x_ai", "andrew_ng", "sam_altman", "elon_musk", "ilya_sutskever", "anil_seth", "demis_hassabis", "jensen_huang", "dario_amodei", "mit", "mit_csail", "building_32", "building_23", "deepmind", "google_deepmind", "deeplearning_ai", "ssi", "agi", "superintelligence", "consciousness", "scaling_laws", "ai_agents", "robotics", "llm"}
_EVENT_TERMS = {"launch", "launched", "release", "released", "unveil", "unveiled", "unveils", "introduce", "introduced", "introduces", "announce", "announced", "partnership", "partner", "partners", "acquire", "acquisition", "funding", "investment", "invest", "course", "paper", "research", "study", "model", "product", "platform", "startup", "company", "appointment", "appointed", "joins", "founded", "project", "initiative", "conversation", "interview", "keynote", "podcast", "scaling", "consciousness", "accelerator", "chip", "benchmark", "deployment", "departure_event", "انتشار", "عرضه", "معرفی", "اعلام", "همکاری", "سرمایه", "دوره", "پژوهش", "مطالعه", "مدل", "محصول"}
_PERSONNEL_TERMS = {"people", "person", "veterans", "veteran", "researchers", "researcher", "leaders", "leader", "employees", "employee", "staff", "workers", "worker", "scientists", "scientist", "پژوهشگران", "پژوهشگر", "مدیران", "مدیر", "کارکنان", "کارمند", "نیروها", "نیرو", "افراد"}
_RELATED_CONCEPT_GROUPS = ({"accelerator", "chip", "hardware", "semiconductor"}, {"course", "training", "education", "curriculum"}, {"agent", "agents", "ai_agents", "autonomous"}, {"physical", "world", "environment", "robotics"})


def _normalize_text(text):
    text = str(text or "").lower().replace("ي", "ی").replace("ك", "ک").replace("‌", " ").replace("ه‌ای", "هایی")
    for source, target in sorted(_ALIASES.items(), key=lambda x: len(x[0]), reverse=True): text = text.replace(source, target)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z\u0600-\u06FF0-9_]+", " ", text)).strip()


def _tokenize(text): return {w for w in re.findall(r"[a-zA-Z\u0600-\u06FF0-9_]+", _normalize_text(text)) if w not in _STOPWORDS and len(w) > 2}

def _anchors(text): return _tokenize(text) & _ANCHOR_SET

def _events(text): return _tokenize(text) & _EVENT_TERMS

def _personnel(text): return _tokenize(text) & _PERSONNEL_TERMS

def _numbers(text): return set(re.findall(r"\b\d+(?:\.\d+)?\b", _normalize_text(text)))

def get_signature(title): return sorted(_tokenize(title))


def get_story_signature(item):
    if isinstance(item, str): title, summary, why, leader = item, "", "", ""
    else:
        title = item.get("title", "")
        summary = item.get("summary", "") or item.get("description", "") or item.get("content", "")
        why = item.get("why_it_matters", "") or item.get("why", "")
        leader = item.get("leader", "") or item.get("watch_person", "")
    context_text = " ".join((str(title), str(summary), str(why)))
    leader_text = str(leader or "").strip()
    return {"title": sorted(_tokenize(title)), "title_text": _normalize_text(title), "context": sorted(_tokenize(context_text)), "anchors": sorted(_anchors(context_text + " " + leader_text)), "events": sorted(_events(context_text)), "personnel": sorted(_personnel(context_text)), "numbers": sorted(_numbers(context_text)), "leader": _normalize_text(leader_text) if leader_text else ""}


def encode_story_signature(item): return SEMANTIC_MARKER + json.dumps(get_story_signature(item), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _decode_signature(value):
    if isinstance(value, dict): return value
    if isinstance(value, list): return {"title": list(value), "context": list(value), "anchors": [], "events": [], "personnel": [], "numbers": [], "leader": ""}
    if isinstance(value, str) and value.startswith(SEMANTIC_MARKER):
        try:
            data = json.loads(value[len(SEMANTIC_MARKER):])
            if isinstance(data, dict): return data
        except (TypeError, ValueError, json.JSONDecodeError): pass
    return None


def _jaccard(a, b):
    a, b = set(a or []), set(b or [])
    return len(a & b) / len(a | b) if a and b else 0.0


def _containment(a, b):
    a, b = set(a or []), set(b or [])
    if not a or not b: return 0.0
    inter = len(a & b)
    return max(inter / len(a), inter / len(b))


def _related_concept_match(a, b):
    a, b = set(a or []), set(b or [])
    return any(a & group and b & group for group in _RELATED_CONCEPT_GROUPS)


@dataclass(frozen=True)
class _Overlap:
    title_j: float
    context_j: float
    title_c: float
    context_c: float
    sequence: float
    anchor_j: float
    event_j: float
    number_j: float
    shared_anchors: int
    shared_events: int
    shared_title_tokens: int
    shared_personnel: int
    leader_match: bool
    numbers_a: set
    numbers_b: set
    anchors_a: set
    anchors_b: set
    title_a_tokens: set
    title_b_tokens: set
    context_a_tokens: set
    context_b_tokens: set


def _signature_pair(sig_a, sig_b) -> tuple[dict, dict]:
    return (
        _decode_signature(sig_a) or get_story_signature(str(sig_a)),
        _decode_signature(sig_b) or get_story_signature(str(sig_b)),
    )


def _overlap(a, b) -> _Overlap:
    at, bt = set(a.get("title", [])), set(b.get("title", []))
    ac, bc = set(a.get("context", [])), set(b.get("context", []))
    aa, ba = set(a.get("anchors", [])), set(b.get("anchors", []))
    ae, be = set(a.get("events", [])), set(b.get("events", []))
    ap, bp = set(a.get("personnel", [])), set(b.get("personnel", []))
    an, bn = set(a.get("numbers", [])), set(b.get("numbers", []))
    leader_a, leader_b = str(a.get("leader", "") or ""), str(b.get("leader", "") or "")
    raw_a = str(a.get("title_text", "")) or " ".join(sorted(at))
    raw_b = str(b.get("title_text", "")) or " ".join(sorted(bt))
    return _Overlap(
        title_j=_jaccard(at, bt),
        context_j=_jaccard(ac, bc),
        title_c=_containment(at, bt),
        context_c=_containment(ac, bc),
        sequence=difflib.SequenceMatcher(None, raw_a, raw_b).ratio() if raw_a and raw_b else 0.0,
        anchor_j=_jaccard(aa, ba),
        event_j=_jaccard(ae, be),
        number_j=_jaccard(an, bn),
        shared_anchors=len(aa & ba),
        shared_events=len(ae & be),
        shared_title_tokens=len(at & bt),
        shared_personnel=len(ap & bp),
        leader_match=bool(leader_a and leader_b and leader_a == leader_b),
        numbers_a=an,
        numbers_b=bn,
        anchors_a=aa,
        anchors_b=ba,
        title_a_tokens=at,
        title_b_tokens=bt,
        context_a_tokens=ac,
        context_b_tokens=bc,
    )


def _base_score(o: _Overlap) -> float:
    return o.context_j * 0.34 + o.title_j * 0.24 + max(o.context_c, o.title_c) * 0.12 + o.anchor_j * 0.16 + o.event_j * 0.06 + o.sequence * 0.05 + o.number_j * 0.03


def _anchor_bonus(score: float, o: _Overlap) -> float:
    if o.shared_anchors >= 2:
        score += 0.25
    elif o.shared_anchors >= 1 and o.shared_events >= 1:
        score += 0.18
    if o.leader_match and o.context_j >= 0.20:
        score += 0.14
    return score


def _rewrite_floors(score: float, o: _Overlap) -> tuple[float, dict[str, bool]]:
    if o.numbers_a and o.numbers_b and o.numbers_a != o.numbers_b and o.shared_title_tokens >= 2:
        score = min(score, 0.42)
    rewritten_title_match = bool(o.numbers_a and o.numbers_b and o.numbers_a == o.numbers_b) and o.shared_title_tokens >= 2 and o.sequence >= 0.70
    if rewritten_title_match:
        score = max(score, 0.72)
    close_rewrite_match = not o.numbers_a and not o.numbers_b and o.shared_title_tokens >= 2 and (o.sequence >= 0.62 or o.context_j >= 0.25) and (o.shared_events >= 1 or o.context_j >= 0.20)
    if close_rewrite_match:
        score = max(score, 0.68)
    leader_rewrite_match = o.leader_match and o.context_j >= 0.20 and (o.title_j >= 0.10 or o.sequence >= 0.35)
    if leader_rewrite_match:
        score = max(score, 0.68)
    related_object_match = o.shared_anchors >= 1 and o.shared_title_tokens >= 1 and _related_concept_match(o.title_a_tokens | o.context_a_tokens, o.title_b_tokens | o.context_b_tokens) and o.context_j >= 0.16
    if related_object_match:
        score = max(score, 0.66)
    # Cross-source organizational events need more than a shared company name.
    # A shared event class plus personnel/leadership language provides the
    # semantic bridge while keeping unrelated product/research stories distinct.
    organizational_personnel_event = o.shared_anchors >= 1 and o.shared_events >= 1 and o.shared_personnel >= 1 and (o.context_j >= 0.10 or o.shared_title_tokens >= 2)
    if organizational_personnel_event:
        score = max(score, 0.75)
    if o.shared_anchors >= 1 and o.shared_events >= 1 and o.context_j >= 0.14:
        score = max(score, 0.70)
    return score, {
        "rewritten_title": rewritten_title_match,
        "close_rewrite": close_rewrite_match,
        "leader_rewrite": leader_rewrite_match,
        "related_object": related_object_match,
    }


def _generic_ai_cap(score: float, o: _Overlap, flags: dict[str, bool]) -> float:
    if o.shared_anchors == 1 and o.anchors_a == {"ai"} and not any(flags.values()):
        score = min(score, 0.42)
    return min(1.0, score)


def _similarity(sig_a, sig_b):
    a, b = _signature_pair(sig_a, sig_b)
    overlap = _overlap(a, b)
    score = _anchor_bonus(_base_score(overlap), overlap)
    score, flags = _rewrite_floors(score, overlap)
    return _generic_ai_cap(score, overlap, flags)


def _story_similarity(title_a, title_b): return _similarity(title_a, title_b)

def is_semantic_duplicate(title, recent_signatures, threshold=0.5):
    sig = get_story_signature(title)
    return any(_similarity(sig, rec) >= threshold for rec in recent_signatures)


def deduplicate_semantically(items, history_signatures, threshold=0.45):
    accepted, accepted_items = [], []; accepted_signatures = list(history_signatures or []); rejected_history = rejected_current = 0
    ordered = sorted(list(items or []), key=lambda x: (int(x.get("leader_priority", 0) or 0), float(x.get("editorial_score", 0) or 0), float(x.get("signal_score", 0) or 0), str(x.get("published", ""))), reverse=True)
    for item in ordered:
        signature = get_story_signature(item)
        if max((_similarity(signature, rec) for rec in accepted_signatures), default=0.0) >= threshold:
            rejected_history += 1; continue
        if max((_similarity(signature, get_story_signature(prior)) for prior in accepted_items), default=0.0) >= max(0.50, threshold):
            rejected_current += 1; continue
        accepted.append(item); accepted_items.append(item); accepted_signatures.append(signature)
    print(f"[Story Dedup] {rejected_history} مورد تکراری با تاریخچه و {rejected_current} روایت تکراری در همین اجرا حذف شد؛ {len(accepted)} Story باقی ماند.")
    return accepted
