"""Canonical Story Identity for Radar publication deduplication.

This module is intentionally small and dependency-free. It defines one stable
identity representation for a story so discovery, historical publication
checks, and future Story clustering do not invent competing identifiers.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src",
}
_EDITORIAL_PREFIX_RE = re.compile(r"^(exclusive|breaking|latest|new|update)\s*[|:\-]\s*", re.IGNORECASE)


def canonical_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        query = [
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in _TRACKING_PARAMS
        ]
        path = re.sub(r"/+", "/", parts.path or "/").rstrip("/") or "/"
        return urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), "")
        )
    except Exception:
        return raw.split("#", 1)[0].strip().rstrip("/")


def normalize_title(value: object) -> str:
    text = str(value or "").strip().lower()
    text = _EDITORIAL_PREFIX_RE.sub("", text)
    text = text.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def story_id(item: dict) -> str:
    """Return the stable exact-story identity used by the publication ledger."""
    title = normalize_title(item.get("title", ""))
    if not title:
        return ""
    return hashlib.sha256(title.encode("utf-8")).hexdigest()


def url_id(item: dict) -> str:
    canonical = canonical_url(item.get("canonical_url") or item.get("link") or item.get("url"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest() if canonical else ""
