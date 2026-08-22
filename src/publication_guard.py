"""Final, fail-closed publication gate shared with pre-ranking."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "data" / "telegram_feedback.json"

_TRACKING = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src",
}


def _canonical_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        p = urlsplit(raw)
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _TRACKING]
        path = re.sub(r"/+", "/", p.path or "/").rstrip("/") or "/"
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(sorted(query)), ""))
    except Exception:
        return raw.split("#", 1)[0].rstrip("/")


def _plain(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\u2066", " ").replace("\u2067", " ").replace("\u2069", " ").replace("\u200f", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _telegram_lines(text: str) -> list[str]:
    raw = html.unescape(str(text or ""))
    raw = re.sub(r"</(?:blockquote|b|i|div|p)>", "\n", raw, flags=re.I)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = raw.replace("\u2066", "").replace("\u2067", "").replace("\u2069", "").replace("\u200f", "")
    return [re.sub(r"\s+", " ", x).strip() for x in raw.splitlines() if x.strip()]


def _extract_candidate(text: str) -> tuple[str, str]:
    lines = _telegram_lines(text)
    if not lines:
        return "", ""
    title = lines[0].lstrip("📡 ").strip()
    summary = ""
    for index, line in enumerate(lines):
        if "خلاصه" in line:
            parts = line.split("خلاصه", 1)
            if len(parts) == 2 and parts[1].strip():
                summary = parts[1].strip(" :")
            elif index + 1 < len(lines):
                summary = lines[index + 1]
            break
    return title, summary


def _normalized_title(value: str) -> str:
    text = str(value or "").lower().replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_records() -> list[dict]:
    try:
        data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        messages = data.get("messages", {}) if isinstance(data, dict) else {}
        return [x for x in messages.values() if isinstance(x, dict)] if isinstance(messages, dict) else []
    except Exception as exc:
        if LEDGER_PATH.exists():
            print(f"[Final Publication Guard] ledger unreadable: {exc}; publication BLOCKED", flush=True)
            raise RuntimeError("Publication ledger is unreadable") from exc
        return []


def _semantic_conflict(candidate_title: str, candidate_summary: str, record: dict) -> float:
    try:
        from semantic_dedup import _similarity, get_story_signature
        from semantic_publication_guard import cross_language_anchor_conflict
    except Exception:
        return 0.0
    stored_title = str(record.get("title") or "")
    stored_summary = str(record.get("summary") or record.get("description") or "")
    leader = str(record.get("leader") or record.get("watch_person") or "")
    candidate_text = f"{candidate_title} {candidate_summary}"
    stored_text = f"{stored_title} {stored_summary}"
    candidate = get_story_signature({"title": candidate_title, "summary": candidate_summary})
    stored = get_story_signature({"title": stored_title, "summary": stored_summary})
    score = _similarity(candidate, stored)
    if cross_language_anchor_conflict(candidate_text, stored_text):
        score = max(score, 0.70)
    if leader and _normalized_title(leader) in _normalized_title(candidate_text):
        leader_sig = get_story_signature({"title": f"{leader} {candidate_title}", "summary": candidate_summary})
        stored_sig = get_story_signature({"title": f"{leader} {stored_title}", "summary": stored_summary})
        score = max(score, _similarity(leader_sig, stored_sig))
    return score


def check_before_publish(text: str, source_link: str = "") -> tuple[bool, str]:
    """Return (allowed, reason). Any known publication conflict blocks delivery."""
    records = _load_records()
    if not records:
        return True, "ledger_empty"

    candidate_title, candidate_summary = _extract_candidate(text)
    candidate_url = _canonical_url(source_link)
    title_key = _normalized_title(candidate_title)

    for record in records:
        record_url = _canonical_url(record.get("link", ""))
        if candidate_url and record_url and candidate_url == record_url:
            return False, "canonical_url_already_published"
        stored_title = _normalized_title(record.get("title", ""))
        if title_key and stored_title and title_key == stored_title:
            return False, "exact_story_title_already_published"

    for record in records:
        if not str(record.get("title") or "").strip():
            continue
        score = _semantic_conflict(candidate_title, candidate_summary, record)
        if score >= 0.70:
            return False, f"semantic_story_already_published score={score:.3f}"

    return True, "no_publication_conflict"
