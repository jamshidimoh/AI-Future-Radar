"""Fast, bounded publication-history index shared by ranking and delivery.

Exact canonical URL/title identities remain all-time. Expensive semantic checks are
restricted to the most recent 30 days (maximum 200 records) and at most 10
pre-filtered comparisons per candidate.
"""
from __future__ import annotations

import difflib
import logging
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.canonical_story import canonical_url, normalize_title, url_id
from src.event_identity import event_features
from src.semantic_dedup import get_story_signature
from src.state_io import load_json_state

logger = logging.getLogger(__name__)

DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[1] / "data" / "telegram_feedback.json"
SEMANTIC_LOOKBACK_DAYS = 30
SEMANTIC_HISTORY_LIMIT = 200
MAX_SEMANTIC_COMPARISONS = 10

_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_FROZEN: set[str] = set()
_CACHE_LIMIT = 8


def _path_key(path: str | Path | None) -> str:
    return str(Path(path or DEFAULT_LEDGER_PATH).expanduser().resolve())


def _file_stamp(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


def _record_timestamp(record: dict[str, Any]) -> float:
    for key in ("posted_at", "published_at", "published", "pubDate", "date", "timestamp", "created_at", "sent_at"):
        value = record.get(key)
        if value in (None, ""):
            continue
        try:
            if isinstance(value, (int, float)) or str(value).strip().isdigit():
                stamp = float(value)
                if stamp > 10_000_000_000:
                    stamp /= 1000.0
                if stamp > 0:
                    return stamp
        except (TypeError, ValueError, OverflowError):
            pass
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
    return 0.0


def _person_key(record: dict[str, Any]) -> str:
    return str(
        record.get("person_name")
        or record.get("watch_person")
        or record.get("leader")
        or ""
    ).strip().casefold()


def _semantic_features(record: dict[str, Any]) -> dict[str, Any]:
    signature = get_story_signature(record)
    event_data = event_features(record)
    return {
        "record": record,
        "anchors": set(signature.get("anchors") or []),
        "title_text": str(signature.get("title_text") or normalize_title(record.get("title", ""))),
        "events": set(event_data.get("events") or []),
        "timestamp": _record_timestamp(record),
    }


class PublicationIndex:
    """All-time exact indexes plus a small, recency-bounded semantic window."""

    def __init__(self, records: list[dict[str, Any]] | None = None, *, now: float | None = None):
        started = time.perf_counter()
        self.records = [record for record in (records or []) if isinstance(record, dict)]
        self.record_count = len(self.records)
        self.url_keys: set[str] = set()
        self.url_hashes: set[str] = set()
        self.title_keys: set[str] = set()
        self.people_bootstrap_keys: set[str] = set()

        timestamped: list[tuple[float, int, dict[str, Any]]] = []
        untimestamped: list[tuple[int, dict[str, Any]]] = []
        has_timestamped_records = False
        cutoff = (now if now is not None else time.time()) - SEMANTIC_LOOKBACK_DAYS * 86400

        for position, record in enumerate(self.records):
            if str(record.get("content_type") or "").strip().casefold() in {"education", "educational"}:
                continue
            url = canonical_url(record.get("link") or record.get("url") or record.get("canonical_url") or "")
            title = normalize_title(record.get("title") or "")
            if url:
                self.url_keys.add(url)
                self.url_hashes.add(url_id({"canonical_url": url}))
            if title:
                self.title_keys.add(title)
            if record.get("people_lane"):
                person = _person_key(record)
                if person:
                    self.people_bootstrap_keys.add(person)

            stamp = _record_timestamp(record)
            if stamp:
                has_timestamped_records = True
                if stamp >= cutoff:
                    timestamped.append((stamp, position, record))
            else:
                untimestamped.append((position, record))

        timestamped.sort(key=lambda row: (row[0], row[1]), reverse=True)
        selected = timestamped[:SEMANTIC_HISTORY_LIMIT]
        # Legacy ledgers may predate posted_at. Fall back to insertion order
        # only when the entire ledger lacks timestamps; never mix unknown-age
        # stories into an otherwise date-bounded semantic window.
        remaining = max(0, SEMANTIC_HISTORY_LIMIT - len(selected))
        if remaining and not has_timestamped_records:
            selected.extend((0.0, position, record) for position, record in untimestamped[-remaining:])
        selected.sort(key=lambda row: (row[0], row[1]), reverse=True)

        self.semantic_records = [record for _, _, record in selected]
        self.semantic_rows = [_semantic_features(record) for record in self.semantic_records]
        self.semantic_window_count = len(self.semantic_records)
        self.semantic_window_oldest = min((stamp for stamp, _, _ in selected if stamp), default=0.0)
        self.build_seconds = time.perf_counter() - started

        logger.info(
            "[Publication Index] records=%d exact_urls=%d exact_titles=%d people=%d "
            "semantic_window=%d lookback_days=%d max_comparisons=%d build_ms=%.1f",
            self.record_count,
            len(self.url_keys),
            len(self.title_keys),
            len(self.people_bootstrap_keys),
            self.semantic_window_count,
            SEMANTIC_LOOKBACK_DAYS,
            MAX_SEMANTIC_COMPARISONS,
            self.build_seconds * 1000,
        )

    def contains_url(self, value: str) -> bool:
        key = canonical_url(value)
        return bool(key and key in self.url_keys)

    def contains_title(self, value: str) -> bool:
        key = normalize_title(value)
        return bool(key and key in self.title_keys)

    def has_people_person(self, value: str) -> bool:
        key = str(value or "").strip().casefold()
        return bool(key and key in self.people_bootstrap_keys)

    def add_record(self, record: dict[str, Any]) -> None:
        """Incrementally add a current-run story without rebuilding the index."""
        if not isinstance(record, dict):
            return
        self.records.append(record)
        self.record_count += 1
        if str(record.get("content_type") or "").strip().casefold() in {"education", "educational"}:
            return
        url = canonical_url(record.get("link") or record.get("url") or record.get("canonical_url") or "")
        title = normalize_title(record.get("title") or "")
        if url:
            self.url_keys.add(url)
            self.url_hashes.add(url_id({"canonical_url": url}))
        if title:
            self.title_keys.add(title)
        if record.get("people_lane"):
            person = _person_key(record)
            if person:
                self.people_bootstrap_keys.add(person)
        self.semantic_records.append(record)
        self.semantic_rows.append(_semantic_features(record))
        if len(self.semantic_records) > SEMANTIC_HISTORY_LIMIT:
            self.semantic_records.pop(0)
            self.semantic_rows.pop(0)
        self.semantic_window_count = len(self.semantic_records)

    def semantic_candidates(
        self,
        candidate: dict[str, Any],
        *,
        additional_records: list[dict[str, Any]] | None = None,
        limit: int = MAX_SEMANTIC_COMPARISONS,
    ) -> list[dict[str, Any]]:
        """Cheaply pre-filter and rank likely matches before expensive comparison."""
        maximum = max(0, min(int(limit), MAX_SEMANTIC_COMPARISONS))
        if maximum == 0:
            return []

        candidate_signature = get_story_signature(candidate)
        candidate_anchors = set(candidate_signature.get("anchors") or [])
        candidate_title = str(candidate_signature.get("title_text") or normalize_title(candidate.get("title", "")))
        candidate_events = set(event_features(candidate).get("events") or [])
        candidate_person = _person_key(candidate)
        ranked: list[tuple[float, int, dict[str, Any]]] = []

        rows = list(self.semantic_rows)
        existing_ids = {id(row["record"]) for row in self.semantic_rows}
        if isinstance(additional_records, PublicationIndex):
            for row in additional_records.semantic_rows:
                if id(row["record"]) not in existing_ids:
                    rows.append(row)
                    existing_ids.add(id(row["record"]))
        else:
            for record in additional_records or []:
                if isinstance(record, dict) and id(record) not in existing_ids:
                    rows.append(_semantic_features(record))
                    existing_ids.add(id(record))

        for position, row in enumerate(rows):
            record = row["record"]
            if not str(record.get("title") or "").strip():
                continue
            shared_anchors = candidate_anchors & row["anchors"]
            title_ratio = (
                difflib.SequenceMatcher(None, candidate_title, row["title_text"]).ratio()
                if candidate_title and row["title_text"]
                else 0.0
            )
            shared_events = candidate_events & row["events"]
            same_person = bool(candidate_person and candidate_person == _person_key(record))

            # Same person is only a candidate-generation hint; the protected
            # story comparator still decides whether the event is actually same.
            if len(shared_anchors) < 2 and title_ratio < 0.75 and not (shared_anchors and shared_events) and not same_person:
                continue

            score = (len(shared_anchors) * 2.0) + title_ratio + (len(shared_events) * 0.5) + (10.0 if same_person else 0.0)
            ranked.append((score, position, record))

        ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [record for _, _, record in ranked[:maximum]]


def _load_index(path: str | Path | None = None) -> PublicationIndex:
    key = _path_key(path)
    cached = _CACHE.get(key)
    if cached is not None and key in _FROZEN:
        _CACHE.move_to_end(key)
        return cached["index"]

    resolved = Path(key)
    stamp = _file_stamp(resolved)
    if cached is not None and cached["stamp"] == stamp:
        _CACHE.move_to_end(key)
        return cached["index"]

    data = load_json_state(resolved, {}, label="publication ledger")
    messages = data.get("messages", {}) if isinstance(data, dict) else {}
    records = [item for item in messages.values() if isinstance(item, dict)] if isinstance(messages, dict) else []
    index = PublicationIndex(records)
    _CACHE[key] = {"stamp": stamp, "records": records, "index": index}
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_LIMIT:
        old_key, _ = _CACHE.popitem(last=False)
        _FROZEN.discard(old_key)
    return index


def get_publication_index(
    path: str | Path | None = None,
    *,
    records: list[dict[str, Any]] | None = None,
) -> PublicationIndex:
    """Return the shared cached index, or build an isolated index for supplied records."""
    if records is not None:
        return PublicationIndex(records)
    return _load_index(path)


def load_publication_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    return get_publication_index(path).records


def freeze_publication_index(path: str | Path | None = None) -> PublicationIndex:
    """Freeze the ledger snapshot for one production run.

    New sends are tracked separately by the orchestrator's current-run list, so
    rewriting the JSON ledger after each send must not trigger a full reload.
    """
    index = get_publication_index(path)
    _FROZEN.add(_path_key(path))
    return index


def clear_publication_index_cache(path: str | Path | None = None) -> None:
    if path is None:
        _CACHE.clear()
        _FROZEN.clear()
        return
    key = _path_key(path)
    _CACHE.pop(key, None)
    _FROZEN.discard(key)
