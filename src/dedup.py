"""Canonical publication deduplication with hybrid event identity."""
import json
import logging
import os
import time

from src.canonical_story import canonical_url, normalize_title, story_id, url_id
from src.event_identity import compare_events
from src.semantic_dedup import SEMANTIC_MARKER, _decode_signature, _overlap, _rewrite_floors, _similarity, encode_story_signature, get_signature, get_story_signature
from src.semantic_threshold import semantic_threshold
from src.state_io import load_json_state

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "seen.json")
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "telegram_feedback.json")
MAX_HISTORY = 3000
MAX_SIGNATURE_HISTORY = 1200
MAX_SOURCE_HISTORY = 1000
PROTECTED_MARKER = "__protected_sent__:"
STORY_MARKER = "__story_id__:"
EVENT_MARKER = "__event_identity__:"


def _canonical_url(link): return canonical_url(link)
def _hash_link(link): return url_id({"link": link})
def _normalize_story_title(title): return normalize_title(title)
def _story_id(item): return story_id(item)


def _load_state():
    data = load_json_state(STATE_FILE, {}, label="seen state")
    return data if isinstance(data, dict) else {}


def _load_feedback_records():
    data = load_json_state(FEEDBACK_FILE, {}, label="Telegram feedback state")
    messages = data.get("messages", {}) if isinstance(data, dict) else {}
    return [m for m in messages.values() if isinstance(m, dict)] if isinstance(messages, dict) else []


def _reconcile_feedback(seen_hashes, seen_signatures):
    records = _load_feedback_records()
    if not records: return seen_hashes, seen_signatures, 0
    before_h, before_s = len(seen_hashes), len(seen_signatures)
    for record in records:
        title, link = str(record.get("title", "") or "").strip(), str(record.get("link", "") or "").strip()
        if link: seen_hashes.add(_hash_link(link))
        if title:
            item = dict(record); item["title"] = title
            identity = _story_id(item)
            if identity: seen_signatures.append(STORY_MARKER + identity)
            try: seen_signatures.append(encode_story_signature(item))
            except Exception as exc: logger.warning("Could not encode reconciled feedback story: %s", exc, exc_info=True)
    return seen_hashes, seen_signatures, (len(seen_hashes)-before_h)+(len(seen_signatures)-before_s)


def _signature_key(value):
    if isinstance(value, str): return value
    try: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError): return repr(value)


def _unique_signatures(signatures):
    unique, seen = [], set()
    for value in signatures or []:
        key = _signature_key(value)
        if key in seen: continue
        seen.add(key); unique.append(value)
    return unique[-MAX_SIGNATURE_HISTORY:]


def load_seen():
    data = _load_state(); signatures = data.get("seen_signatures", []) if isinstance(data.get("seen_signatures", []), list) else []; hashes = data.get("seen_hashes", []) if isinstance(data.get("seen_hashes", []), list) else []
    hashes, signatures, added = _reconcile_feedback(set(hashes), signatures)
    if added: print(f"[Publication Ledger] reconciled={added} identities from Telegram history", flush=True)
    return hashes, _unique_signatures(signatures)


def load_source_history():
    history = _load_state().get("source_history", []); return history if isinstance(history, list) else []


def save_seen(seen_hashes, seen_signatures, source_history=None):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if source_history is None: source_history = load_source_history()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen_hashes": list(dict.fromkeys(seen_hashes))[-MAX_HISTORY:], "seen_signatures": _unique_signatures(seen_signatures), "source_history": source_history[-MAX_SOURCE_HISTORY:]}, f, ensure_ascii=False, indent=2)


def _is_protected_leader(item): return bool(item.get("protected_content") or item.get("_named_leader_interview") or item.get("leader_watch_protected"))
def _is_leader_exception(item): return bool(item.get("protected_content") and (item.get("leader") or item.get("watch_person") or item.get("_named_leader_interview") or item.get("leader_watch_protected")))
def _is_education(item): return str(item.get("content_type") or "").strip().lower() == "education"


def _education_identity(item):
    value = item.get("education_id")
    try: return f"education:{int(value)}" if value is not None else ""
    except (TypeError, ValueError): return ""


def _stored_story_ids(signatures): return {s[len(STORY_MARKER):] for s in signatures if isinstance(s, str) and s.startswith(STORY_MARKER)}
def _stored_protected_hashes(signatures): return {s[len(PROTECTED_MARKER):] for s in signatures if isinstance(s, str) and s.startswith(PROTECTED_MARKER)}

def _stored_title_signature_match(item, signatures):
    candidate = tuple(get_signature(item.get("title", "")))
    if not candidate:
        return False
    return any(
        tuple(value) == candidate
        for value in signatures or []
        if isinstance(value, list) and all(isinstance(token, str) for token in value)
    )


def _protected_leader_rewrite_match(item, signatures):
    if not _is_leader_exception(item):
        return False
    candidate = get_story_signature(item)
    leader = str(candidate.get("leader") or "").strip()
    title = set(candidate.get("title") or [])
    context = set(candidate.get("context") or [])
    if not leader or not title:
        return False
    for stored in signatures or []:
        if not isinstance(stored, str) or not stored.startswith(SEMANTIC_MARKER):
            continue
        prior = _decode_signature(stored)
        if not isinstance(prior, dict) or str(prior.get("leader") or "").strip() != leader:
            continue
        prior_title = set(prior.get("title") or [])
        prior_context = set(prior.get("context") or [])
        shared_title = len(title & prior_title)
        context_overlap = _similarity(candidate, prior)
        if shared_title >= 2 and context_overlap >= 0.66:
            return True
        if shared_title >= 3 and len(context & prior_context) >= 4:
            return True
    return False


def _event_history(signatures):
    out=[]
    for value in signatures or []:
        if not isinstance(value,str) or not value.startswith(EVENT_MARKER): continue
        try:
            data=json.loads(value[len(EVENT_MARKER):])
            if isinstance(data,dict): out.append(data)
        except (TypeError, ValueError) as exc: logger.warning("Ignoring malformed event history signature: %s", exc, exc_info=True)
    return out


def _legacy_event_history(signatures):
    out=[]
    for value in signatures or []:
        if not isinstance(value,str) or not value.startswith(SEMANTIC_MARKER): continue
        data=_decode_signature(value)
        if not isinstance(data,dict): continue
        title=str(data.get("title_text") or " ".join(data.get("title") or []))
        out.append({"title":title,"tokens":data.get("context") or data.get("title") or [],"event_time":None,"entities":data.get("anchors") or [],"events":data.get("events") or [],"material":[]})
    return out


def _event_payload(item):
    from src.event_identity import event_features
    data=dict(event_features(item)); data["time"]=data.get("time").isoformat() if data.get("time") else None
    for key in ("entities","events","tokens","material"): data[key]=sorted(data.get(key) or [])
    return data


def _event_match(item, signatures):
    try:
        previous_items=[]
        for previous in _event_history(signatures): previous_items.append({"title":previous.get("title", ""),"summary":" ".join(previous.get("tokens", [])),"event_time":previous.get("time") or previous.get("event_time")})
        previous_items.extend({"title":p.get("title",""),"summary":" ".join(p.get("tokens", []))} for p in _legacy_event_history(signatures))
        for prior in previous_items:
            kind,score,_=compare_events(item,prior)
            if kind=="DUPLICATE": return True,score
        if _is_leader_exception(item):
            candidate = get_story_signature(item)
            for stored in signatures or []:
                if isinstance(stored, str) and stored.startswith(SEMANTIC_MARKER) and _similarity(candidate, stored) >= 0.45: return True, 0.45
    except Exception as exc: logger.warning("Event identity history match unavailable: %s", exc, exc_info=True)
    return False,0.0


def _semantic_publication_match(candidate_signature, stored_signature):
    """Use a lower semantic floor only when the scorer identifies a rewrite pattern."""
    if not isinstance(stored_signature, str) or not stored_signature.startswith(SEMANTIC_MARKER): return False
    candidate = _decode_signature(candidate_signature) or get_story_signature(str(candidate_signature))
    stored = _decode_signature(stored_signature) or get_story_signature(str(stored_signature))
    overlap = _overlap(candidate, stored)
    score = _similarity(candidate, stored)
    if score < 0.66: return False
    _, flags = _rewrite_floors(score, overlap)
    return any(flags.values())


def _semantic_history_match(item, signatures):
    candidate=get_story_signature(item); best=0.0
    for stored in signatures or []:
        if not isinstance(stored,str) or not stored.startswith(SEMANTIC_MARKER): continue
        score=_similarity(candidate,stored); best=max(best,score)
        if _semantic_publication_match(candidate,stored): return score
    return best


def filter_new_items(items, seen_hashes):
    _,seen_signatures=load_seen(); stored_story_ids=_stored_story_ids(seen_signatures); protected_hashes=_stored_protected_hashes(seen_signatures)
    result=[]; local_event_items=[]; local_semantic=[]
    rejected_url=rejected_story=rejected_semantic=0; protected_event_blocked=0
    for item in items or []:
        if _is_education(item):
            identity=_education_identity(item)
            if identity and identity in stored_story_ids: rejected_story+=1; continue
            result.append(item); continue
        link_hash,identity=_hash_link(item.get("link", "")),_story_id(item)
        if link_hash in seen_hashes or (_is_protected_leader(item) and link_hash in protected_hashes): rejected_url+=1; continue
        if identity and identity in stored_story_ids: rejected_story+=1; continue
        if _stored_title_signature_match(item, seen_signatures):
            rejected_story += 1
            if _is_protected_leader(item):
                protected_event_blocked += 1
            continue
        if _protected_leader_rewrite_match(item, seen_signatures):
            rejected_semantic += 1
            protected_event_blocked += 1
            continue
        matched,_score=_event_match(item,seen_signatures)
        if matched:
            rejected_semantic+=1
            if _is_protected_leader(item): protected_event_blocked+=1
            continue
        if any(compare_events(item,previous)[0]=="DUPLICATE" for previous in local_event_items): rejected_semantic+=1; continue
        candidate_sig=get_story_signature(item)
        if not _is_leader_exception(item) and any(_semantic_publication_match(candidate_sig,s) for s in seen_signatures if isinstance(s,str) and s.startswith(SEMANTIC_MARKER)):
            rejected_semantic+=1; continue
        local_match=max((_similarity(candidate_sig,p) for p in local_semantic),default=0.0)
        local_rewrite_match=any(_semantic_publication_match(candidate_sig,p) for p in local_semantic)
        if local_rewrite_match or local_match>=semantic_threshold(item,local=True): rejected_semantic+=1; continue
        local_semantic.append(encode_story_signature(item)); local_event_items.append(dict(item)); result.append(item)
    print(f"[Canonical Story Gate] kept={len(result)} | url_rejected={rejected_url} | story_rejected={rejected_story} | semantic_rejected={rejected_semantic} | protected_event_blocked={protected_event_blocked}")
    return result


def mark_as_seen(item, seen_hashes, seen_signatures, source_history=None):
    from src.semantic_dedup import get_signature
    if _is_education(item):
        identity=_education_identity(item)
        if identity: seen_signatures.append(STORY_MARKER+identity)
        if source_history is not None: source_history.append({"ts":int(time.time()),"source":item.get("source","education"),"category":item.get("category","ai"),"mission_area":item.get("mission_area",""),"content_type":"education","leader":"","story_id":identity})
        return seen_hashes,seen_signatures,source_history
    link_hash,identity=_hash_link(item.get("link", "")),_story_id(item); seen_hashes.add(link_hash)
    if _is_protected_leader(item): seen_signatures.append(PROTECTED_MARKER+link_hash)
    if identity: seen_signatures.append(STORY_MARKER+identity)
    seen_signatures.append(get_signature(item.get("title", ""))); seen_signatures.append(encode_story_signature(item))
    try: seen_signatures.append(EVENT_MARKER+json.dumps(_event_payload(item),ensure_ascii=False,sort_keys=True,separators=(",",":")))
    except Exception as exc: logger.warning("Could not encode event identity history: %s", exc, exc_info=True)
    if source_history is not None: source_history.append({"ts":int(time.time()),"source":item.get("source","unknown"),"category":item.get("category","ai"),"mission_area":item.get("mission_area",""),"content_type":item.get("content_type","news"),"leader":item.get("leader") or item.get("watch_person") or item.get("_leader_match", ""),"story_id":identity})
    return seen_hashes,seen_signatures,source_history