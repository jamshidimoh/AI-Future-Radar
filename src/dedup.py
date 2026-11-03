"""Canonical publication deduplication with hybrid event identity."""
import json
import logging
import os
import time

from src.canonical_story import canonical_url, normalize_title, story_id, url_id
from src.event_identity import compare_events
from src.publication_index import PublicationIndex, freeze_publication_index, get_publication_index, load_publication_records
from src.semantic_dedup import SEMANTIC_MARKER, _decode_signature, _overlap, _rewrite_floors, _similarity, encode_story_signature, get_story_signature
from src.state_io import load_json_state

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "seen.json")
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "telegram_feedback.json")
MAX_HISTORY = 3000
MAX_SIGNATURE_HISTORY = 1200
MAX_SOURCE_HISTORY = 1000
MAX_DEDUP_SEMANTIC_HISTORY = 200
_STATE_CACHE = {}
PROTECTED_MARKER = "__protected_sent__:"
STORY_MARKER = "__story_id__:"
EVENT_MARKER = "__event_identity__:"


def _canonical_url(link): return canonical_url(link)
def _hash_link(link): return url_id({"link": link})
def _normalize_story_title(title): return normalize_title(title)
def _story_id(item): return story_id(item)


def _load_state():
    path = os.path.abspath(STATE_FILE)
    try:
        stat = os.stat(path)
        stamp = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = None
    cached = _STATE_CACHE.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    data = load_json_state(STATE_FILE, {}, label="seen state")
    result = data if isinstance(data, dict) else {}
    _STATE_CACHE[path] = (stamp, result)
    return result


def _load_feedback_records():
    return load_publication_records(FEEDBACK_FILE)


def freeze_feedback_history():
    """Freeze the all-time Telegram ledger snapshot for the active production run."""
    return freeze_publication_index(FEEDBACK_FILE)


def _reconcile_feedback(seen_hashes, seen_signatures):
    # The shared index builds exact URL identities for the entire ledger once.
    # The set merge is cheap; no historic message records are re-parsed or scanned.
    index = get_publication_index(FEEDBACK_FILE)
    before_h, before_s = len(seen_hashes), len(seen_signatures)
    seen_hashes.update(index.url_hashes)
    for record in index.semantic_records:
        title = str(record.get("title", "") or "").strip()
        if not title:
            continue
        item = dict(record)
        item["title"] = title
        identity = _story_id(item)
        if identity:
            seen_signatures.append(STORY_MARKER + identity)
        try:
            seen_signatures.append(encode_story_signature(item))
        except Exception as exc:
            logger.warning("Could not encode reconciled feedback story: %s", exc, exc_info=True)
        try:
            seen_signatures.append(EVENT_MARKER + json.dumps(_event_payload(item), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        except Exception as exc:
            logger.warning("Could not encode reconciled event identity: %s", exc, exc_info=True)
    return seen_hashes, _unique_signatures(seen_signatures), (len(seen_hashes) - before_h) + (len(seen_signatures) - before_s)

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
    _STATE_CACHE.pop(os.path.abspath(STATE_FILE), None)


def _is_protected_leader(item): return bool(item.get("protected_content") or item.get("_named_leader_interview") or item.get("leader_watch_protected"))
def _is_leader_exception(item): return bool(item.get("protected_content") and (item.get("leader") or item.get("watch_person") or item.get("_named_leader_interview") or item.get("leader_watch_protected")))
def _is_education(item): return str(item.get("content_type") or "").strip().lower() == "education"


def _education_identity(item):
    value = item.get("education_id")
    try: return f"education:{int(value)}" if value is not None else ""
    except (TypeError, ValueError): return ""


def _stored_story_ids(signatures): return {s[len(STORY_MARKER):] for s in signatures if isinstance(s, str) and s.startswith(STORY_MARKER)}
def _stored_protected_hashes(signatures): return {s[len(PROTECTED_MARKER):] for s in signatures if isinstance(s, str) and s.startswith(PROTECTED_MARKER)}


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
    semantic_history = [value for value in signatures or [] if isinstance(value, str) and value.startswith(SEMANTIC_MARKER)][-MAX_DEDUP_SEMANTIC_HISTORY:]
    for stored in semantic_history:
        score=_similarity(candidate,stored); best=max(best,score)
        if _semantic_publication_match(candidate,stored): return score
    return best


def _signature_history_records(signatures):
    records = []
    semantic_values = [value for value in signatures or [] if isinstance(value, str) and value.startswith(SEMANTIC_MARKER)][-MAX_DEDUP_SEMANTIC_HISTORY:]
    for value in semantic_values:
        decoded = _decode_signature(value)
        if not isinstance(decoded, dict):
            continue
        title = str(decoded.get("title_text") or " ".join(decoded.get("title") or [])).strip()
        if not title:
            continue
        leader = str(decoded.get("leader") or "").replace("_", " ").strip()
        records.append({
            "title": title,
            "summary": " ".join(decoded.get("context") or []),
            "leader": leader,
            "watch_person": leader,
        })
    return records


def filter_new_items(items, seen_hashes):
    loaded_hashes, seen_signatures = load_seen()
    effective_seen_hashes = set(seen_hashes or []) | set(loaded_hashes or [])
    stored_story_ids = _stored_story_ids(seen_signatures)
    protected_hashes = _stored_protected_hashes(seen_signatures)
    ledger_index = get_publication_index(FEEDBACK_FILE)
    if ledger_index.semantic_records:
        history_index = ledger_index
    elif not ledger_index.record_count:
        # State-only legacy recovery for installations whose Telegram ledger
        # has not yet been populated.
        history_index = PublicationIndex(_signature_history_records(seen_signatures))
    else:
        history_index = PublicationIndex([])
    local_index = PublicationIndex([])
    result = []
    rejected_url = rejected_story = rejected_semantic = 0
    protected_event_blocked = semantic_comparisons = 0

    for item in items or []:
        if _is_education(item):
            identity = _education_identity(item)
            if identity and identity in stored_story_ids:
                rejected_story += 1
                continue
            result.append(item)
            continue

        candidate_url = item.get("canonical_url") or item.get("link") or item.get("url") or ""
        link_hash, identity = _hash_link(candidate_url), _story_id(item)
        if (
            link_hash in effective_seen_hashes
            or ledger_index.contains_url(candidate_url)
            or local_index.contains_url(candidate_url)
            or (_is_protected_leader(item) and link_hash in protected_hashes)
        ):
            rejected_url += 1
            continue
        if identity and (
            identity in stored_story_ids
            or ledger_index.contains_title(item.get("title", ""))
            or local_index.contains_title(item.get("title", ""))
        ):
            rejected_story += 1
            continue

        candidate_signature = get_story_signature(item)
        comparisons = history_index.semantic_candidates(
            item, additional_records=local_index, limit=10
        )
        semantic_comparisons += len(comparisons)
        matched = False
        for previous in comparisons:
            event_kind, _, _ = compare_events(item, previous)
            previous_signature = get_story_signature(previous)
            if event_kind == "DUPLICATE":
                matched = True
            elif event_kind == "UPDATE":
                matched = False
            elif _is_leader_exception(item):
                candidate_leader = str(candidate_signature.get("leader") or "").strip()
                previous_leader = str(previous_signature.get("leader") or "").strip()
                matched = bool(
                    candidate_leader
                    and candidate_leader == previous_leader
                    and _similarity(candidate_signature, previous_signature) >= 0.45
                )
            else:
                matched = _semantic_publication_match(candidate_signature, encode_story_signature(previous))
            if matched:
                break

        if matched:
            rejected_semantic += 1
            if _is_protected_leader(item):
                protected_event_blocked += 1
            continue

        local_index.add_record(dict(item))
        result.append(item)

    print(
        f"[Canonical Story Gate] kept={len(result)} | url_rejected={rejected_url} | "
        f"story_rejected={rejected_story} | semantic_rejected={rejected_semantic} | "
        f"protected_event_blocked={protected_event_blocked} | semantic_comparisons={semantic_comparisons} "
        f"max_per_candidate=10 history_window={history_index.semantic_window_count}"
    )
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