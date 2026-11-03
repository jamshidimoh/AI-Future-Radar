"""Indexed and bounded publication-history access.

Exact URL/title identities remain available for the full Telegram ledger.
Expensive semantic comparisons use only recent, bounded publication records.
"""
from __future__ import annotations

import difflib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.canonical_story import canonical_url
from src.event_identity import event_features
from src.semantic_dedup import SEMANTIC_MARKER, get_story_signature
from src.state_io import load_json_state

logger = logging.getLogger(__name__)

SEMANTIC_WINDOW_DAYS = 30
MAX_SEMANTIC_RECORDS = 200
MAX_SEMANTIC_COMPARISONS = 30

_RECORD_CACHE: dict[str, tuple[tuple[int, int] | None, list[dict[str, Any]]]] = {}
_INDEX_CACHE: dict[tuple[Any, ...], PublicationIndex] = {}


def normalize_publication_title(value: object) -> str:
    """Normalize a title exactly as the publication guard historically did."""
    import re

    text = str(value or "").lower().replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _path_key(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def _fingerprint(path: str | Path) -> tuple[int, int] | None:
    try:
        stat = Path(path).stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


def load_feedback_records(path: str | Path) -> list[dict[str, Any]]:
    """Load the Telegram ledger once per unchanged file version."""
    key = _path_key(path)
    fingerprint = _fingerprint(path)
    cached = _RECORD_CACHE.get(key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]

    data = load_json_state(Path(path), {}, label="Telegram publication history")
    messages = data.get("messages", {}) if isinstance(data, dict) else {}
    records = [item for item in messages.values() if isinstance(item, dict)] if isinstance(messages, dict) else []
    _RECORD_CACHE[key] = (fingerprint, records)
    return records


def clear_publication_caches() -> None:
    """Reset process-local caches at the beginning of a production run."""
    _RECORD_CACHE.clear()
    _INDEX_CACHE.clear()


def _posted_at(record: dict[str, Any]) -> float | None:
    value = record.get("posted_at") or record.get("timestamp") or record.get("date")
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
        if numeric > 0:
            return numeric
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _profile(item: dict[str, Any]) -> tuple[dict[str, Any], set[str], str]:
    signature = get_story_signature(item)
    anchors = set(signature.get("anchors") or [])
    title_text = str(signature.get("title_text") or "")
    return signature, anchors, title_text


class PublicationIndex:
    """Full-history exact index plus a bounded semantic comparison window."""

    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        *,
        now: float | None = None,
        window_days: int = SEMANTIC_WINDOW_DAYS,
        max_records: int = MAX_SEMANTIC_RECORDS,
    ) -> None:
        self.records: list[dict[str, Any]] = (
            records if isinstance(records, list) and all(isinstance(x, dict) for x in records)
            else [x for x in (records or []) if isinstance(x, dict)]
        )
        self.now = float(now if now is not None else time.time())
        self.window_days = max(1, int(window_days))
        self.max_records = max(1, int(max_records))
        self.semantic_requests = 0
        self.prefilter_checks = 0
        self.semantic_comparisons = 0
        self._rebuild()

    def _rebuild(self) -> None:
        self.urls: dict[str, dict[str, Any]] = {}
        self.titles: dict[str, dict[str, Any]] = {}
        self.people_lane_names: set[str] = set()

        for record in self.records:
            link = canonical_url(record.get("link") or record.get("url") or "")
            title = normalize_publication_title(record.get("title") or "")
            if link:
                self.urls.setdefault(link, record)
            if title:
                self.titles.setdefault(title, record)
            if record.get("people_lane"):
                person = str(
                    record.get("person_name") or record.get("watch_person") or record.get("leader") or ""
                ).strip()
                if person:
                    self.people_lane_names.add(person.casefold())

        dated: list[tuple[float, dict[str, Any]]] = []
        has_any_timestamp = False
        for record in self.records:
            timestamp = _posted_at(record)
            if timestamp is not None:
                has_any_timestamp = True
                if self.now - self.window_days * 86400 <= timestamp <= self.now + 86400:
                    dated.append((timestamp, record))

        if dated:
            recent = [record for _, record in sorted(dated, key=lambda pair: pair[0], reverse=True)]
        elif has_any_timestamp:
            # A timestamped but old ledger must not fall back into the semantic window.
            recent = []
        else:
            # Fixtures and old migrated ledgers may not have posted_at. Use
            # insertion order only when the entire ledger is undated.
            recent = list(self.records)
        self.semantic_records = recent[: self.max_records]
        self._semantic_entries: list[tuple[dict[str, Any], set[str], str, set[str], set[str], float]] = []
        self._encoded_signatures: dict[int, str] = {}
        for record in self.semantic_records:
            try:
                signature, anchors, title_text = _profile(record)
                self._encoded_signatures[id(record)] = SEMANTIC_MARKER + json.dumps(
                    signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                features = event_features(record)
                entities = set(features.get("entities") or [])
                events = set(features.get("events") or [])
                self._semantic_entries.append(
                    (record, anchors, title_text, entities, events, _posted_at(record) or 0.0)
                )
            except Exception as exc:
                logger.debug("Skipping malformed semantic history record: %s", exc)

    def add_record(self, record: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            return
        link = canonical_url(record.get("link") or record.get("url") or "")
        title = normalize_publication_title(record.get("title") or "")
        if any(
            link and canonical_url(existing.get("link") or existing.get("url") or "") == link
            and normalize_publication_title(existing.get("title") or "") == title
            for existing in self.records[-20:]
        ):
            return
        self.records.append(dict(record))
        self._rebuild()

    def has_url(self, value: object) -> bool:
        link = canonical_url(value)
        return bool(link and link in self.urls)

    def url_record(self, value: object) -> dict[str, Any] | None:
        return self.urls.get(canonical_url(value)) if value else None

    def has_title(self, value: object) -> bool:
        title = normalize_publication_title(value)
        return bool(title and title in self.titles)

    def title_record(self, value: object) -> dict[str, Any] | None:
        return self.titles.get(normalize_publication_title(value))

    def has_people_person(self, value: object) -> bool:
        person = str(value or "").strip().casefold()
        return bool(person and person in self.people_lane_names)

    def semantic_candidates(
        self,
        item: dict[str, Any],
        *,
        extra_records: list[dict[str, Any]] | None = None,
        limit: int = MAX_SEMANTIC_COMPARISONS,
    ) -> list[dict[str, Any]]:
        """Return up to the comparison cap of likely records."""
        self.semantic_requests += 1
        cap = max(1, min(int(limit), MAX_SEMANTIC_COMPARISONS))
        try:
            _candidate_signature, candidate_anchors, candidate_title = _profile(item)
        except Exception as exc:
            logger.debug("Could not profile semantic publication candidate: %s", exc)
            candidate_anchors, candidate_title = set(), ""

        candidate_features = event_features(item)
        candidate_entities = set(candidate_features.get("entities") or [])
        candidate_events = set(candidate_features.get("events") or [])
        entries = list(self._semantic_entries)
        known = {
            (canonical_url(record.get("link") or record.get("url") or ""),
             normalize_publication_title(record.get("title") or ""))
            for record, *_ in entries
        }
        for record in extra_records or []:
            if not isinstance(record, dict):
                continue
            identity = (
                canonical_url(record.get("link") or record.get("url") or ""),
                normalize_publication_title(record.get("title") or ""),
            )
            if identity in known:
                continue
            known.add(identity)
            try:
                _signature, anchors, title_text = _profile(record)
                features = event_features(record)
                entities = set(features.get("entities") or [])
                events = set(features.get("events") or [])
                entries.append((record, anchors, title_text, entities, events, _posted_at(record) or self.now))
            except Exception as exc:
                logger.debug("Skipping malformed runtime semantic record: %s", exc)

        ranked: list[tuple[float, float, dict[str, Any]]] = []
        fallback: list[tuple[float, dict[str, Any]]] = []
        for record, anchors, title_text, entities, events, timestamp in entries:
            self.prefilter_checks += 1
            shared_anchors = len(candidate_anchors & anchors)
            shared_entities = len(candidate_entities & entities)
            shared_events = len(candidate_events & events)
            title_similarity = (
                difflib.SequenceMatcher(None, candidate_title, title_text).ratio()
                if candidate_title and title_text else 0.0
            )
            score = shared_anchors * 2.0 + shared_entities * 1.5 + shared_events * 1.5 + title_similarity
            fallback.append((timestamp, record))
            event_prefilter = shared_events > 0 and (
                shared_anchors > 0 or shared_entities > 0 or title_similarity >= 0.55
            )
            if shared_anchors >= 2 or event_prefilter or title_similarity >= 0.75:
                ranked.append((score, timestamp, record))

        ranked.sort(key=lambda value: (value[0], value[1]), reverse=True)
        selected: list[dict[str, Any]] = []
        selected_ids: set[int] = set()
        for _score, _timestamp, record in ranked:
            if id(record) not in selected_ids:
                selected.append(record)
                selected_ids.add(id(record))
            if len(selected) >= cap:
                break

        # Fill unused slots from recent history to preserve recall for
        # low-overlap or cross-language rewrites. Detailed work stays capped.
        if len(selected) < cap:
            fallback.sort(key=lambda value: value[0], reverse=True)
            for _timestamp, record in fallback:
                if id(record) in selected_ids:
                    continue
                selected.append(record)
                selected_ids.add(id(record))
                if len(selected) >= cap:
                    break
        return selected

    def semantic_signature(self, record: dict[str, Any]) -> str:
        """Return the precomputed signature used by semantic comparison."""
        value = self._encoded_signatures.get(id(record))
        if value is not None:
            return value
        signature = get_story_signature(record)
        value = SEMANTIC_MARKER + json.dumps(
            signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        self._encoded_signatures[id(record)] = value
        return value

    def note_comparison(self, count: int = 1) -> None:
        self.semantic_comparisons += max(0, int(count))

    def metrics(self) -> dict[str, int]:
        return {
            "ledger_records": len(self.records),
            "semantic_window_records": len(self.semantic_records),
            "semantic_requests": self.semantic_requests,
            "prefilter_checks": self.prefilter_checks,
            "semantic_comparisons": self.semantic_comparisons,
        }


def cached_publication_index(
    records: list[dict[str, Any]],
    *,
    cache_key: tuple[Any, ...],
) -> PublicationIndex:
    key = (*cache_key, id(records))
    index = _INDEX_CACHE.get(key)
    if index is None:
        index = PublicationIndex(records)
        _INDEX_CACHE[key] = index
        if len(_INDEX_CACHE) > 16:
            for stale_key in list(_INDEX_CACHE)[:-8]:
                _INDEX_CACHE.pop(stale_key, None)
    return index


def remember_feedback_record(path: str | Path, record: dict[str, Any]) -> None:
    """Update process-local history/index after a confirmed Telegram delivery."""
    key = _path_key(path)
    cached = _RECORD_CACHE.get(key)
    current_fingerprint = _fingerprint(path)
    # A confirmed-delivery callback may have just persisted this message (or
    # another collector may have updated feedback); reload the changed version.
    records = cached[1] if cached is not None and cached[0] == current_fingerprint else load_feedback_records(path)

    link = canonical_url(record.get("link") or record.get("url") or "")
    title = normalize_publication_title(record.get("title") or "")
    duplicate_exists = any(
        link and canonical_url(existing.get("link") or existing.get("url") or "") == link
        and normalize_publication_title(existing.get("title") or "") == title
        for existing in records[-20:]
    )
    if not duplicate_exists:
        records.append(dict(record))

    _RECORD_CACHE[key] = (_fingerprint(path), records)
    # A delivery callback may have changed the persisted ledger after the index
    # was first built. Rebind every index for this ledger path to the latest
    # record list and rebuild it immediately, preserving counters and sharing.
    for index_key, index in list(_INDEX_CACHE.items()):
        if not index_key or index_key[0] != key:
            continue
        _INDEX_CACHE.pop(index_key, None)
        index.records = records
        index._rebuild()
        _INDEX_CACHE[(*index_key[:-1], id(records))] = index
