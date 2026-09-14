"""Final, fail-closed publication gate shared with ranking and delivery."""
from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.event_identity import compare_events, events
from src.semantic_dedup import _similarity, get_story_signature
from src.semantic_publication_guard import shared_anchor_count
from src.state_io import load_json_state

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "data" / "telegram_feedback.json"

_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def _canonical_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        p = urlsplit(raw)
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _TRACKING]
        path = re.sub(r"/+", "/", p.path or "/").rstrip("/") or "/"
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(sorted(query)), ""))
    except (ValueError, AttributeError) as exc:
        logger.warning("Could not canonicalize publication URL %s: %s", raw, exc, exc_info=True)
        return raw.split("#", 1)[0].rstrip("/")


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
    data = load_json_state(LEDGER_PATH, {}, label="publication ledger")
    messages = data.get("messages", {}) if isinstance(data, dict) else {}
    return [x for x in messages.values() if isinstance(x, dict)] if isinstance(messages, dict) else []


def _semantic_conflict(candidate_title: str, candidate_summary: str, record: dict) -> float:
    """Return semantic conflict only with strong, corroborated same-story evidence."""
    stored_title = str(record.get("title") or "")
    stored_summary = str(record.get("summary") or record.get("description") or "")
    candidate = {"title": candidate_title, "summary": candidate_summary}
    stored = {"title": stored_title, "summary": stored_summary}
    normalized_candidate_summary = _normalized_title(candidate_summary)
    normalized_stored_summary = _normalized_title(stored_summary)
    if normalized_candidate_summary and normalized_candidate_summary == normalized_stored_summary:
        return 1.0

    kind, event_score, evidence = compare_events(candidate, stored)
    semantic_score = _similarity(get_story_signature(candidate), get_story_signature(stored))
    anchors = shared_anchor_count(f"{candidate_title} {candidate_summary}", f"{stored_title} {stored_summary}")
    shared_events = set(evidence.get("shared_events") or [])
    shared_events |= events(f"{candidate_title} {candidate_summary}") & events(f"{stored_title} {stored_summary}")
    title_similarity = float(evidence.get("title_similarity", 0.0) or 0.0)
    context_jaccard = float(evidence.get("context_jaccard", 0.0) or 0.0)

    if kind == "UPDATE":
        if anchors >= 3 and shared_events and semantic_score >= 0.65:
            return 1.0
        if title_similarity >= 0.90 and context_jaccard >= 0.45:
            return 1.0
        return 0.0
    if kind == "DUPLICATE":
        # A high raw semantic score alone is not sufficient: unrelated stories
        # about the same entity/topic can score highly. Require corroboration
        # from concrete anchors + the same event class, or very strong title and
        # context identity. This preserves distinct events such as IPO vs model
        # launch while still blocking cross-source rewrites.
        if shared_events and anchors >= 3 and semantic_score >= 0.65:
            return 1.0
        if title_similarity >= 0.90 and context_jaccard >= 0.45:
            return 1.0
        return 0.0

    # Cross-language rewrites often have low lexical/semantic similarity. Shared
    # concrete anchors plus the same event class are sufficient; the previous
    # 0.45 event-score threshold incorrectly rejected this class of duplicate.
    if anchors >= 3 and shared_events and (event_score >= 0.20 or semantic_score >= 0.65):
        return 1.0
    if anchors >= 2 and title_similarity >= 0.82 and context_jaccard >= 0.35:
        return 0.85

    logger.debug(
        "publication semantic comparison kind=%s anchors=%d semantic=%.3f event=%.3f title=%.3f context=%.3f shared_events=%s evidence=%s",
        kind,
        anchors,
        semantic_score,
        event_score,
        title_similarity,
        context_jaccard,
        sorted(shared_events),
        evidence,
    )
    return 0.0


def check_before_publish(text: str, source_link: str = "", records: list[dict] | None = None) -> tuple[bool, str]:
    """Return (allowed, reason). Known same-story publications block delivery."""
    stored_records = _load_records()
    runtime_records = [x for x in (records or []) if isinstance(x, dict)]
    all_records = runtime_records + stored_records
    if not all_records:
        return True, "ledger_empty"
    candidate_title, candidate_summary = _extract_candidate(text)
    candidate_url = _canonical_url(source_link)
    title_key = _normalized_title(candidate_title)
    for record in all_records:
        record_url = _canonical_url(record.get("link", ""))
        if candidate_url and record_url and candidate_url == record_url:
            return False, "canonical_url_already_published"
        stored_title = _normalized_title(record.get("title", ""))
        if title_key and stored_title and title_key == stored_title:
            return False, "exact_story_title_already_published"
    for record in all_records:
        if not str(record.get("title") or "").strip():
            continue
        score = _semantic_conflict(candidate_title, candidate_summary, record)
        if score >= 0.82:
            return False, f"semantic_story_already_published score={score:.3f}"
    return True, "no_publication_conflict"
