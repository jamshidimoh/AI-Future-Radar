"""Simple People Signal lane: bootstrap once, then track every new independent signal."""
# ruff: noqa: I001
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.dedup import _hash_link
from src.story_identity import deduplicate_stories


MISSION_TERMS = (
    "artificial intelligence", "ai", "agi", "machine learning", "llm",
    "foundation model", "agent", "agents", "robotics", "humanoid",
    "quantum", "quantum computing", "brain-computer", "bci", "neurotechnology",
    "consciousness", "cognition", "neuroscience", "philosophy of mind",
    "philosophy of science", "future of ai", "futur", "genetics", "genomics",
    "crispr", "synthetic biology", "protein", "education", "learning",
    "technology", "science", "digital transformation", "ai safety",
    "alignment", "governance", "singularity", "intelligence",
    "هوش مصنوعی", "آگاهی", "شناخت", "کوانتوم", "ژنتیک", "آموزش",
)


def load_people_watchlist(path: str | Path) -> list[str]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    people = payload.get("people", {}) if isinstance(payload, dict) else {}
    names: list[str] = []
    if isinstance(people, dict):
        for cfg in people.values():
            if not isinstance(cfg, dict):
                continue
            for raw in cfg.get("names", []) or []:
                name = str(raw).strip()
                if name and name not in names:
                    names.append(name)
    if len(names) != 30:
        raise ValueError(f"People Watchlist must contain exactly 30 people; found {len(names)}")
    return names


def parse_time(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            continue
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _item_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in (
            "title", "summary", "description", "category", "topic_family",
            "content_type", "discovery_query", "watch_query", "speaker",
            "speakers", "author", "guest", "interviewee",
        )
    ).casefold()


def person_for_item(item: dict[str, Any], people: list[str]) -> str:
    explicit = " ".join(
        str(item.get(key) or "")
        for key in ("watch_person", "leader", "person_name", "person", "speaker", "speakers")
    ).strip().casefold()
    if explicit:
        for person in people:
            if person.casefold() in explicit:
                return person
    text = _item_text(item)
    for person in sorted(people, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(person.casefold())}(?!\w)", text):
            return person
    return ""


def _contains_mission_term(text: str) -> bool:
    for term in MISSION_TERMS:
        # "ai" is too short for substring matching: "daily", "email", "trail",
        # and many unrelated words contain those two letters. Treat it as a
        # standalone token while retaining substring matching for established
        # multi-character mission terms and the "futur" stem.
        if term == "ai":
            if re.search(r"(?<![a-z0-9_])ai(?![a-z0-9_])", text, flags=re.IGNORECASE):
                return True
            continue
        if term in text:
            return True
    return False


def relevant_people_item(item: dict[str, Any], person: str) -> bool:
    text = _item_text(item)
    if person.casefold() not in text and str(item.get("watch_person") or "").casefold() != person.casefold():
        return False
    ctype = str(item.get("content_type") or "").casefold()
    if _contains_mission_term(text):
        return True
    # Discovery queries describe search intent, not article evidence. A generated
    # People query deliberately contains mission terms, so trusting them here
    # can turn an unrelated result into a false-positive People signal.
    return ctype in {
        "interview", "podcast", "talk", "lecture", "conversation",
        "discussion", "q&a", "research", "essay", "commentary",
    } and bool(person)


def item_timestamp(item: dict[str, Any]) -> float:
    for key in ("published", "published_at", "pubDate", "date", "updated", "timestamp"):
        parsed = parse_time(item.get(key))
        if parsed is not None:
            return parsed
    return 0.0


def identity(item: dict[str, Any]) -> str:
    return str(item.get("canonical_url") or item.get("link") or item.get("url") or item.get("title") or "").strip()


def mark_people_item(item: dict[str, Any], person: str, *, bootstrap: bool = False) -> dict[str, Any]:
    out = dict(item)
    out["people_lane"] = True
    out["people_signal"] = True
    out["person_name"] = person
    out["watch_person"] = person
    out["leader"] = person
    out["is_leader_watch"] = True
    out["leader_watch_protected"] = True
    out["people_bootstrap"] = bool(bootstrap)
    return out


def _seen_hash_set(seen_hashes: Any) -> set[str]:
    return {str(x) for x in (seen_hashes or []) if isinstance(x, str)}


def _is_seen_identity(value: str, seen_hashes: set[str]) -> bool:
    if not value:
        return False
    try:
        return _hash_link(value) in seen_hashes
    except Exception:
        return False


def bootstrap_candidates(
    items: list[dict[str, Any]],
    people: list[str],
    *,
    previous_state: dict[str, Any] | None = None,
    seen_hashes: Any = None,
) -> list[dict[str, Any]]:
    """Return one latest eligible item per person, preserving the same baseline on retry."""
    previous_state = previous_state or {}
    baseline = previous_state.get("baseline", {}) if isinstance(previous_state, dict) else {}
    delivered = set(previous_state.get("delivered_people", []) or []) if isinstance(previous_state, dict) else set()
    chosen: list[dict[str, Any]] = []
    for person in people:
        if person in delivered:
            continue
        prior = baseline.get(person, {}) if isinstance(baseline, dict) else {}
        prior_link = str(prior.get("link") or "").strip() if isinstance(prior, dict) else ""
        pool = [
            dict(item)
            for item in items
            if person_for_item(item, people) == person and relevant_people_item(item, person)
        ]
        if not pool:
            continue
        if prior_link:
            exact = [item for item in pool if identity(item) == prior_link]
            if exact:
                chosen.append(mark_people_item(exact[0], person, bootstrap=True))
                continue
        # Bootstrap deliberately ignores the global seen-state: it establishes
        # the baseline content for each watched person, even when that content
        # was previously encountered elsewhere in Radar.
        ranked = list(pool)
        ranked.sort(key=lambda item: item_timestamp(item), reverse=True)
        chosen.append(mark_people_item(ranked[0], person, bootstrap=True))
    return chosen


def post_bootstrap_candidates(
    items: list[dict[str, Any]],
    people: list[str],
    *,
    bootstrap_at: str,
    seen_hashes: Any = None,
) -> list[dict[str, Any]]:
    checkpoint = parse_time(bootstrap_at)
    if checkpoint is None:
        return []
    seen = _seen_hash_set(seen_hashes)
    out: list[dict[str, Any]] = []
    for item in items:
        person = person_for_item(item, people)
        if not person or not relevant_people_item(item, person):
            continue
        ts = item_timestamp(item)
        if ts <= checkpoint:
            continue
        if _is_seen_identity(identity(item), seen):
            continue
        out.append(mark_people_item(item, person))
    out.sort(key=lambda item: (item_timestamp(item), str(item.get("title") or "")), reverse=True)
    return out


def deduplicate_people_signals(
    items: list[dict[str, Any]],
    *,
    seen_signatures: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Deduplicate within each person while preserving independent people signals."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        person = str(item.get("person_name") or item.get("watch_person") or "").strip()
        grouped.setdefault(person, []).append(item)

    survivors: list[dict[str, Any]] = []
    history = list(seen_signatures or [])
    for person_items in grouped.values():
        unique: list[dict[str, Any]] = []
        seen_local: set[str] = set()
        for item in person_items:
            key = identity(item)
            if key and key in seen_local:
                continue
            if key:
                seen_local.add(key)
            unique.append(item)
        survivors.extend(deduplicate_stories(unique, history=history))

    survivors.sort(key=lambda item: (item_timestamp(item), str(item.get("title") or "")), reverse=True)
    return survivors


def build_bootstrap_state(
    *,
    bootstrap_at: str,
    candidates: list[dict[str, Any]],
    delivered_people: list[str],
    status: str,
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_state = previous_state or {}
    prior_baseline = previous_state.get("baseline", {}) if isinstance(previous_state, dict) else {}
    baseline: dict[str, dict[str, Any]] = dict(prior_baseline) if isinstance(prior_baseline, dict) else {}
    for item in candidates:
        person = str(item.get("person_name") or item.get("watch_person") or "").strip()
        if not person:
            continue
        baseline[person] = {
            "title": str(item.get("title") or "").strip(),
            "link": identity(item),
            "published": str(item.get("published") or "").strip(),
        }
    prior_delivered = previous_state.get("delivered_people", []) if isinstance(previous_state, dict) else []
    cumulative_delivered = set(prior_delivered) | set(delivered_people)
    return {
        "status": status,
        "bootstrap_at": bootstrap_at,
        "baseline": baseline,
        "delivered_people": sorted(cumulative_delivered),
        "people_count": len(baseline),
        "delivered_count": len(cumulative_delivered),
    }
