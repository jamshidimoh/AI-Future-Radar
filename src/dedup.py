"""جلوگیری از تکرار؛ Canonical Story Identity برای Dedup بین منابع و اجراها."""
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


def _stored_story_ids(signatures): return {s[len(STORY_MARKER):] for s in signatures if isinstance(s, str) and s.startswith(STORY_MARKER)}


def _semantic_history_match(item, signatures):
    try:
        from semantic_dedup import get_story_signature, _similarity, SEMANTIC_MARKER
        from semantic_threshold import semantic_threshold
    except Exception:
        return 0.0
    candidate = get_story_signature(item)
    threshold = semantic_threshold(item, local=False)
    best = 0.0
    for stored in signatures or []:
        if not isinstance(stored, str) or not stored.startswith(SEMANTIC_MARKER): continue
        score = _similarity(candidate, stored)
        best = max(best, score)
        if best >= threshold: return best
    return best


def _protected_same_story_match(item, signatures):
    """Detect only strong rewrites of the same protected story, not same-topic items."""
    try:
        from semantic_dedup import SEMANTIC_MARKER, _decode_signature, get_story_signature
        from protected_story_identity import probable_same_story
    except Exception:
        return False
    candidate = get_story_signature(item)
    for stored in signatures or []:
        if not isinstance(stored, str) or not stored.startswith(SEMANTIC_MARKER):
            continue
        stored_signature = _decode_signature(stored)
        if stored_signature and probable_same_story(candidate, stored_signature):
            return True
    return False


def filter_new_items(items, seen_hashes):
    """Single publication gate: canonical URL, exact Story ID, then semantic identity.

    Protected leader material uses a conservative same-story rewrite check instead
    of broad historical topic similarity. This prevents a leader's new interview
    from being starved by older stories about the same person while still blocking
    mirrored/reframed versions of the same story.
    """
    _, seen_signatures = load_seen()
    protected_sent = {s[len(PROTECTED_MARKER):] for s in seen_signatures if isinstance(s, str) and s.startswith(PROTECTED_MARKER)}
    stored_story_ids = _stored_story_ids(seen_signatures)
    result, local_urls, local_stories, local_semantic = [], set(), set(), []
    rejected_url = rejected_story = rejected_semantic = 0
    protected_semantic_bypassed = 0
    protected_same_story_blocked = 0
    for item in items:
        link_hash, identity = _hash_link(item.get("link", "")), _story_id(item)
        protected = _is_protected_leader(item)
        if protected:
            if link_hash in protected_sent or (identity and identity in stored_story_ids):
                rejected_story += 1; continue
            if _protected_same_story_match(item, seen_signatures):
                rejected_semantic += 1
                protected_same_story_blocked += 1
                continue
            protected_semantic_bypassed += 1
        else:
            if link_hash in seen_hashes:
                rejected_url += 1; continue
            if identity and identity in stored_story_ids:
                rejected_story += 1; continue
            semantic_match = _semantic_history_match(item, seen_signatures)
            if semantic_match >= __import__("semantic_threshold").semantic_threshold(item, local=False):
                rejected_semantic += 1; continue
        if link_hash in local_urls or (identity and identity in local_stories):
            rejected_story += 1; continue
        local_match = 0.0
        try:
            from semantic_dedup import get_story_signature, _similarity
            candidate = get_story_signature(item)
            local_match = max((_similarity(candidate, previous) for previous in local_semantic), default=0.0)
        except Exception: pass
        try:
            from semantic_threshold import semantic_threshold
            local_threshold = semantic_threshold(item, local=True)
        except Exception:
            local_threshold = 0.60
        if local_match >= local_threshold:
            rejected_semantic += 1; continue
        local_urls.add(link_hash)
        if identity: local_stories.add(identity)
        try:
            from semantic_dedup import get_story_signature
            local_semantic.append(get_story_signature(item))
        except Exception: pass
        result.append(item)
    print(f"[Canonical Story Gate] kept={len(result)} | url_rejected={rejected_url} | story_rejected={rejected_story} | semantic_rejected={rejected_semantic} | protected_semantic_bypassed={protected_semantic_bypassed} | protected_same_story_blocked={protected_same_story_blocked}")
    return result


def mark_as_seen(item, seen_hashes, seen_signatures, source_history=None):
    from semantic_dedup import encode_story_signature, get_signature
    link_hash, identity = _hash_link(item.get("link", "")), _story_id(item)
    if _is_protected_leader(item): seen_signatures.append(PROTECTED_MARKER + link_hash)
    else: seen_hashes.add(link_hash)
    if identity: seen_signatures.append(STORY_MARKER + identity)
    seen_signatures.append(get_signature(item.get("title", ""))); seen_signatures.append(encode_story_signature(item))
    if source_history is not None:
        source_history.append({"ts": int(time.time()), "source": item.get("source", "unknown"), "category": item.get("category", "ai"), "content_type": item.get("content_type", "news"), "leader": item.get("leader") or item.get("watch_person") or item.get("_leader_match", ""), "story_id": identity})
    return seen_hashes, seen_signatures, source_history
