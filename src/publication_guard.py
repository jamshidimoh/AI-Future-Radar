"""Final, fail-closed publication gate shared with ranking and delivery."""
from __future__ import annotations

import difflib
import html
import logging
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.event_identity import compare_events, events
from src.publication_index import cached_publication_index, load_feedback_records, remember_feedback_record
from src.semantic_dedup import _similarity, get_story_signature
from src.semantic_publication_guard import shared_anchor_count

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "data" / "telegram_feedback.json"

_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src"}

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _title_numeric_identifiers(value: str) -> set[str]:
    """Return non-year numeric identifiers from a title, normalized across digit sets."""
    text = str(value or "").translate(_PERSIAN_DIGITS)
    numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    return {n for n in numbers if not (n.isdigit() and len(n) == 4 and 1900 <= int(n) <= 2100)}



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
    return load_feedback_records(LEDGER_PATH)


def _publication_index():
    records = _load_records()
    return cached_publication_index(
        records,
        cache_key=(str(Path(LEDGER_PATH).resolve()),),
    )


def remember_successful_publication(story: dict) -> None:
    """Refresh exact and semantic indexes after confirmed Telegram delivery."""
    record = {
        "source": story.get("source"),
        "content_type": story.get("content_type"),
        "category": story.get("category"),
        "leader": story.get("leader"),
        "watch_person": story.get("watch_person"),
        "person_name": story.get("person_name"),
        "people_lane": bool(story.get("people_lane")),
        "title": str(story.get("title") or "").strip(),
        "summary": str(story.get("summary") or story.get("description") or "").strip(),
        "description": str(story.get("description") or "").strip(),
        "link": str(story.get("link") or story.get("url") or "").strip(),
        "posted_at": int(time.time()),
    }
    remember_feedback_record(LEDGER_PATH, record)


def _semantic_conflict(candidate_title: str, candidate_summary: str, record: dict) -> float:
    """Return semantic conflict only for a corroborated same story/event.

    Publication history is stricter than discovery dedup: a different publisher
    URL must not allow the same underlying event to be published again. At the
    same time, repeated coverage of the same person/entity must remain allowed
    when the event is materially different.
    """
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
    shared_entities = set(evidence.get("shared_entities") or [])
    semantic_signature_candidate = get_story_signature(candidate)
    semantic_signature_stored = get_story_signature(stored)
    semantic_shared_anchors = set(semantic_signature_candidate.get("anchors") or []) & set(semantic_signature_stored.get("anchors") or [])
    semantic_shared_events = set(semantic_signature_candidate.get("events") or []) & set(semantic_signature_stored.get("events") or [])
    semantic_title_tokens = set(semantic_signature_candidate.get("title") or []) & set(semantic_signature_stored.get("title") or [])
    semantic_title_jaccard = (
        len(semantic_title_tokens)
        / len(set(semantic_signature_candidate.get("title") or []) | set(semantic_signature_stored.get("title") or []))
        if semantic_signature_candidate.get("title") and semantic_signature_stored.get("title")
        else 0.0
    )
    semantic_title_sequence = difflib.SequenceMatcher(
        None,
        str(semantic_signature_candidate.get("title_text") or ""),
        str(semantic_signature_stored.get("title_text") or ""),
    ).ratio()
    shared_title_numeric_identifiers = _title_numeric_identifiers(candidate_title) & _title_numeric_identifiers(stored_title)

    # Material updates are distinct developments and must not be suppressed by
    # otherwise strong title/entity overlap.
    if kind == "UPDATE":
        return 0.0

    # Language-aware title identity is evaluated before other duplicate checks.
    # This catches fully Persian rewrites where Latin/digit anchors are sparse.
    if (
        semantic_shared_anchors
        and semantic_shared_events
        and len(semantic_title_tokens) >= 4
        and semantic_title_jaccard >= 0.30
        and semantic_title_sequence >= 0.60
    ):
        return 1.0

    if kind == "DUPLICATE":
        # Cross-source rewrites are the primary failure mode: one source may
        # mention only one concrete entity while the second source supplies the
        # rest of the context. Do not require three anchors when the event
        # matcher has already classified both stories as the same event.
        # Event classification alone is not enough: different research or
        # product stories from the same entity can share a broad event class.
        # Require corroborating title/context overlap before blocking.
        if shared_events and title_similarity >= 0.72 and context_jaccard >= 0.18:
            return 1.0
        if title_similarity >= 0.90 and context_jaccard >= 0.45:
            return 1.0
        return 0.0

    # Cross-language rewrites can have lower lexical overlap, but concrete
    # anchors alone are still insufficient: unrelated stories from the same
    # organization can share the same broad event class. Require an additional
    # title/context corroboration before blocking this fallback class.
    if (
        anchors >= 2
        and shared_events
        and shared_title_numeric_identifiers
    ):
        return 1.0
    if (
        anchors >= 2
        and shared_events
        and semantic_score >= 0.60
        and (title_similarity >= 0.75 or context_jaccard >= 0.20)
    ):
        return 1.0
    if anchors >= 2 and title_similarity >= 0.82 and context_jaccard >= 0.35:
        return 0.85

    logger.debug(
        "publication semantic comparison kind=%s anchors=%d semantic=%.3f event=%.3f title=%.3f context=%.3f shared_events=%s shared_entities=%s evidence=%s",
        kind,
        anchors,
        semantic_score,
        event_score,
        title_similarity,
        context_jaccard,
        sorted(shared_events),
        sorted(shared_entities),
        evidence,
    )
    return 0.0


def check_before_publish(text: str, source_link: str = "", records: list[dict] | None = None, candidate: dict | None = None) -> tuple[bool, str]:
    """Return (allowed, reason) using one indexed ledger and bounded semantic history."""
    index = _publication_index()
    runtime_records = [x for x in (records or []) if isinstance(x, dict)]
    candidate_data = candidate or {}
    candidate_people_lane = bool(candidate_data.get("people_lane"))
    candidate_people_bootstrap = bool(candidate_data.get("people_bootstrap"))
    candidate_title, candidate_summary = _extract_candidate(text)
    candidate_url = _canonical_url(source_link)
    title_key = _normalized_title(candidate_title)
    candidate_person = str(
        candidate_data.get("person_name")
        or candidate_data.get("watch_person")
        or candidate_data.get("leader")
        or ""
    ).strip()

    if not index.records and not runtime_records:
        return True, "ledger_empty"

    if candidate_people_bootstrap and candidate_person:
        if index.has_people_person(candidate_person):
            return False, "people_bootstrap_person_already_published"
        for record in runtime_records:
            if not record.get("people_lane"):
                continue
            stored_person = str(
                record.get("person_name") or record.get("watch_person") or record.get("leader") or ""
            ).strip()
            if stored_person and stored_person.casefold() == candidate_person.casefold():
                return False, "people_bootstrap_person_already_published"
        return True, "people_bootstrap_baseline"

    if candidate_url and index.has_url(candidate_url):
        return False, "canonical_url_already_published"
    if title_key and index.has_title(title_key):
        return False, "exact_story_title_already_published"
    for record in runtime_records:
        record_url = _canonical_url(record.get("link", ""))
        if candidate_url and record_url and candidate_url == record_url:
            return False, "canonical_url_already_published"
        stored_title = _normalized_title(record.get("title", ""))
        if title_key and stored_title and title_key == stored_title:
            return False, "exact_story_title_already_published"

    semantic_candidate = {"title": candidate_title, "summary": candidate_summary}
    candidates = index.semantic_candidates(semantic_candidate, extra_records=runtime_records, limit=10)
    for record in candidates:
        if not str(record.get("title") or "").strip():
            continue
        if candidate_people_lane and record.get("people_lane"):
            stored_person = str(
                record.get("person_name") or record.get("watch_person") or record.get("leader") or ""
            ).strip()
            if candidate_person and stored_person and candidate_person.casefold() != stored_person.casefold():
                continue
        index.note_comparison()
        score = _semantic_conflict(candidate_title, candidate_summary, record)
        if score >= 0.82:
            return False, f"semantic_story_already_published score={score:.3f}"

    return True, "no_publication_conflict"
