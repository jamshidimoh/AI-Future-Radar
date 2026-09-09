"""Canonical publication deduplication.

URL identity and exact title identity remain terminal fast paths. Cross-source
semantic identity is augmented by event identity; protected leader content no
longer bypasses the event-level duplicate check.
"""
import json
import os
import time

try:
    from .canonical_story import canonical_url, normalize_title, story_id, url_id
except ImportError:
    from canonical_story import canonical_url, normalize_title, story_id, url_id

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "seen.json")
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "telegram_feedback.json")
MAX_HISTORY = 3000
MAX_SIGNATURE_HISTORY = 1200
MAX_SOURCE_HISTORY = 1000
PROTECTED_MARKER = "__protected_sent__:"
STORY_MARKER = "__story_id__:"
EVENT_MARKER = "__event_identity__:"


def _canonical_url(link):
    return canonical_url(link)


def _hash_link(link):
    return url_id({"link": link})


def _normalize_story_title(title):
    return normalize_title(title)


def _story_id(item):
    return story_id(item)


def _load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}


def _load_feedback_records():
    if not os.path.exists(FEEDBACK_FILE): return []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        messages = data.get("messages", {}) if isinstance(data, dict) else {}
        return [m for m in messages.values() if isinstance(m, dict)] if isinstance(messages, dict) else []
    except Exception as exc:
        print(f"[Publication Ledger] feedback history unavailable: {exc}", flush=True); return []


def _reconcile_feedback(seen_hashes, seen_signatures):
    records = _load_feedback_records()
    if not records: return seen_hashes, seen_signatures, 0
    try: from semantic_dedup import encode_story_signature
    except Exception: encode_story_signature = None
    before_h, before_s = len(seen_hashes), len(seen_signatures)
    for record in records:
        title, link = str(record.get("title", "") or "").strip(), str(record.get("link", "") or "").strip()
        if link: seen_hashes.add(_hash_link(link))
        if title:
            item = dict(record); item["title"] = title
            identity = _story_id(item)
            if identity: seen_signatures.append(STORY_MARKER + identity)
            if encode_story_signature:
                try: seen_signatures.append(encode_story_signature(item))
                except Exception: pass
            try:
                from event_identity import event_representation
                seen_signatures.append(EVENT_MARKER + json.dumps(event_representation(item), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            except Exception:
                pass
    added = (len(seen_hashes)-before_h)+(len(seen_signatures)-before_s)
    if added: print(f"[Publication Ledger] reconciled={added} identities from Telegram history", flush=True)
    return seen_hashes, seen_signatures, added


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
    data = _load_state()
    signatures = data.get("seen_signatures", []) if isinstance(data.get("seen_signatures", []), list) else []
    hashes = data.get("seen_hashes", []) if isinstance(data.get("seen_hashes", []), list) else []
    hashes, signatures, _ = _reconcile_feedback(set(hashes), signatures)
    return hashes, _unique_signatures(signatures)


def load_source_history():
    history = _load_state().get("source_history", [])
    return history if isinstance(history, list) else []


def save_seen(seen_hashes, seen_signatures, source_history=None):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if source_history is None: source_history = load_source_history()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen_hashes": list(dict.fromkeys(seen_hashes))[-MAX_HISTORY:], "seen_signatures": _unique_signatures(seen_signatures), "source_history": source_history[-MAX_SOURCE_HISTORY:]}, f, ensure_ascii=False, indent=2)


def _is_protected_leader(item): return bool(item.get("protected_content") or item.get("_named_leader_interview"))


def _is_education(item):
    return str(item.get("content_type") or "").strip().lower() == "education"


def _education_identity(item):
    value = item.get("education_id")
    try:
        return f"education:{int(value)}" if value is not None else ""
    except (TypeError, ValueError):
        return ""


def _stored_story_ids(signatures): return {s[len(STORY_MARKER):] for s in signatures if isinstance(s, str) and s.startswith(STORY_MARKER)}


def _stored_event_representations(signatures):
    out = []
    for value in signatures or []:
        if not isinstance(value, str) or not value.startswith(EVENT_MARKER):
            continue
        try:
            data = json.loads(value[len(EVENT_MARKER):])
            if isinstance(data, dict): out.append(data)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return out


def _semantic_history_match(item, signatures):
    try:
        from semantic_dedup import get_story_signature, _similarity
        from semantic_threshold import semantic_threshold
    except Exception:
        return 0.0
    candidate = get_story_signature(item)
    threshold = semantic_threshold(item, local=False)
    best = 0.0
    for stored in signatures or []:
        if not isinstance(stored, str) or not stored.startswith("__semantic_story__:"): continue
        score = _similarity(candidate, stored)
        best = max(best, score)
        if best >= threshold: return best
    return best


def _event_history_match(item, signatures):
    try:
        from event_identity import classify_story, event_similarity
        candidate = event_representation_for_item(item)
    except Exception:
        return "NEW", 0.0
    best = ("NEW", 0.0)
    for stored in _stored_event_representations(signatures):
        # Stored event representations are canonical feature vectors; classify_story
        # accepts articles, so compare a lightweight synthetic article carrying the
        # representation features through direct similarity instead.
        try:
            score = _event_similarity_from_rep(candidate, stored)
        except Exception:
            score = 0.0
        if score > best[1]:
            best = ("MATCH", score)
    return best


def event_representation_for_item(item):
    from event_identity import event_representation
    return event_representation(item)


def _event_similarity_from_rep(a, b):
    from event_identity import _jaccard, _set
    score = 0.0
    for key, weight in (("organizations", 0.16), ("people", 0.18), ("products", 0.17), ("concepts", 0.24), ("event_types", 0.10), ("tokens", 0.15)):
        score += _jaccard(_set(a, key), _set(b, key)) * weight
    aa, ab = _set(a, "people"), _set(b, "people")
    pa, pb = _set(a, "products"), _set(b, "products")
    oa, ob = _set(a, "organizations"), _set(b, "organizations")
    ca, cb = _set(a, "concepts"), _set(b, "concepts")
    ea, eb = _set(a, "event_types"), _set(b, "event_types")
    if aa & ab and pa & pb and (ea & eb or ca & cb): score = max(score, 0.78)
    if oa & ob and aa & ab and pa & pb: score = max(score, 0.78)
    if oa & ob and len(ca & cb) >= 2 and ea & eb: score = max(score, 0.78)
    if aa & ab and len(ca & cb) >= 2 and ea & eb: score = max(score, 0.78)
    return round(min(1.0, score), 4)


def _event_duplicate(item, signatures):
    try:
        from event_identity import classify_story
        candidate = event_representation_for_item(item)
    except Exception:
        return False, 0.0, "NEW"
    best = 0.0
    for stored in _stored_event_representations(signatures):
        score = _event_similarity_from_rep(candidate, stored)
        best = max(best, score)
        if score >= 0.78:
            # Material-update logic needs the original representation; reconstruct
            # the small comparison directly so new findings do not disappear.
            ca, cb = set(candidate.get("numbers") or []), set(stored.get("numbers") or [])
            ma, mb = set(candidate.get("material") or []), set(stored.get("material") or [])
            material = bool(ca and cb and ca != cb) or len(ma - mb) >= 2 or len(mb - ma) >= 2
            ea, eb = set(candidate.get("event_types") or []), set(stored.get("event_types") or [])
            if ea and eb and ea != eb: material = True
            return (not material), score, "UPDATE" if material else "DUPLICATE"
    return False, best, "NEW"


def filter_new_items(items, seen_hashes):
    """Single publication gate: URL, exact story, event identity, then semantic fallback."""
    _, seen_signatures = load_seen()
    stored_story_ids = _stored_story_ids(seen_signatures)
    result, local_urls, local_stories, local_semantic, local_events = [], set(), set(), [], []
    rejected_url = rejected_story = rejected_semantic = rejected_event = 0
    protected_event_bypassed = 0
    protected_same_story_blocked = 0
    for item in items:
        if _is_education(item):
            identity = _education_identity(item)
            if identity and identity in stored_story_ids:
                rejected_story += 1; continue
            if identity and identity in local_stories:
                rejected_story += 1; continue
            if identity: local_stories.add(identity)
            result.append(item); continue

        link_hash, identity = _hash_link(item.get("link", "")), _story_id(item)
        protected = _is_protected_leader(item)
        if link_hash in seen_hashes:
            rejected_url += 1; continue
        if identity and identity in stored_story_ids:
            rejected_story += 1; continue
        if link_hash in local_urls or (identity and identity in local_stories):
            rejected_story += 1; continue

        is_dup, event_score, event_status = _event_duplicate(item, seen_signatures)
        if is_dup:
            rejected_event += 1; continue
        if event_status == "UPDATE":
            pass

        semantic_match = _semantic_history_match(item, seen_signatures)
        try:
            from semantic_threshold import semantic_threshold
            historical_threshold = semantic_threshold(item, local=False)
        except Exception:
            historical_threshold = 0.68
        if semantic_match >= historical_threshold:
            rejected_semantic += 1; continue

        try:
            from semantic_dedup import get_story_signature, _similarity
            candidate = get_story_signature(item)
            local_match = max((_similarity(candidate, previous) for previous in local_semantic), default=0.0)
        except Exception:
            local_match = 0.0
        try:
            from semantic_threshold import semantic_threshold
            local_threshold = semantic_threshold(item, local=True)
        except Exception:
            local_threshold = 0.60
        if local_match >= local_threshold:
            rejected_semantic += 1; continue

        try:
            from event_identity import event_representation
            candidate_event = event_representation(item)
            if any(_event_similarity_from_rep(candidate_event, previous) >= 0.78 for previous in local_events):
                rejected_event += 1; continue
            local_events.append(candidate_event)
        except Exception:
            pass
        local_urls.add(link_hash)
        if identity: local_stories.add(identity)
        try:
            from semantic_dedup import get_story_signature
            local_semantic.append(get_story_signature(item))
        except Exception: pass
        result.append(item)
    print(f"[Canonical Story Gate] kept={len(result)} | url_rejected={rejected_url} | story_rejected={rejected_story} | semantic_rejected={rejected_semantic} | event_rejected={rejected_event} | protected_semantic_bypassed=0 | protected_same_story_blocked={protected_same_story_blocked}")
    return result


def mark_as_seen(item, seen_hashes, seen_signatures, source_history=None):
    from semantic_dedup import encode_story_signature, get_signature
    if _is_education(item):
        identity = _education_identity(item)
        if identity:
            seen_signatures.append(STORY_MARKER + identity)
        if source_history is not None:
            source_history.append({"ts": int(time.time()), "source": item.get("source", "education"), "category": item.get("category", "ai"), "content_type": "education", "leader": "", "story_id": identity})
        return seen_hashes, seen_signatures, source_history
    link_hash, identity = _hash_link(item.get("link", "")), _story_id(item)
    seen_hashes.add(link_hash)
    if _is_protected_leader(item): seen_signatures.append(PROTECTED_MARKER + link_hash)
    if identity: seen_signatures.append(STORY_MARKER + identity)
    seen_signatures.append(get_signature(item.get("title", ""))); seen_signatures.append(encode_story_signature(item))
    try:
        from event_identity import event_representation
        seen_signatures.append(EVENT_MARKER + json.dumps(event_representation(item), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except Exception:
        pass
    if source_history is not None:
        source_history.append({"ts": int(time.time()), "source": item.get("source", "unknown"), "category": item.get("category", "ai"), "content_type": item.get("content_type", "news"), "leader": item.get("leader") or item.get("watch_person") or item.get("_leader_match", ""), "story_id": identity})
    return seen_hashes, seen_signatures, source_history
