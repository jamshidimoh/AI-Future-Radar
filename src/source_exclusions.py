"""Global source exclusions for discovery and ingestion.

These are hard discovery constraints, not ranking or editorial penalties.
"""

from __future__ import annotations

from urllib.parse import urlparse

EXCLUDED_SOURCE_DOMAINS = frozenset({"arxiv.org", "export.arxiv.org"})
EXCLUDED_SOURCE_MARKERS = frozenset({"arxiv.org", "export.arxiv.org"})


def is_excluded_source_url(value: str | None) -> bool:
    """Return True when a URL belongs to a globally excluded source domain."""
    text = str(value or "").strip().lower()
    if not text:
        return False
    try:
        parsed = urlparse(text if "://" in text else f"https://{text}")
        host = (parsed.hostname or "").lower().rstrip(".")
        return any(host == domain or host.endswith(f".{domain}") for domain in EXCLUDED_SOURCE_DOMAINS)
    except ValueError:
        return any(marker in text for marker in EXCLUDED_SOURCE_MARKERS)


def is_excluded_source_text(value: str | None) -> bool:
    """Return True for discovery text that explicitly targets an excluded source."""
    text = str(value or "").strip().lower()
    return any(marker in text for marker in EXCLUDED_SOURCE_MARKERS)
