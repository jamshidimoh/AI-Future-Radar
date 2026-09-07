"""Deterministic publisher-authority resolution."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_TIER1_DOMAIN_MARKERS = ("openai.com", "anthropic.com", "deepmind.google", "blog.google", "research.google", "hai.stanford.edu", "stanford.edu", "csail.mit.edu", "news.mit.edu", "mit.edu", "nature.com", "ncsu.edu", "cmu.edu", "nvidia.com", "nist.gov", "ieee.org", "quanta.com")
_TIER2_DOMAIN_MARKERS = ("reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "cnbc.com", "forbes.com", "technologyreview.com", "spectrum.ieee.org", "arstechnica.com", "wired.com", "scientificamerican.com", "newscientist.com", "businessinsider.com")
_TIER1_NAME_MARKERS = ("openai", "anthropic", "google deepmind", "mit csail", "mit news", "stanford hai", "stanford university", "nature", "nist", "ieee", "quanta magazine", "carnegie mellon")
_TIER2_NAME_MARKERS = ("reuters", "associated press", "bbc", "cnbc", "forbes", "mit technology review", "ieee spectrum", "ars technica", "wired", "scientific american", "new scientist", "business insider")


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _host(url: object) -> str:
    value = _clean(url)
    if not value:
        return ""
    try:
        return urlparse(value if "://" in value else f"https://{value}").netloc.removeprefix("www.").split(":", 1)[0]
    except Exception:
        return ""


def _domain_match(host: str, markers: tuple[str, ...]) -> bool:
    return any(host == marker or host.endswith(f".{marker}") for marker in markers)


def _name_match(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _configured_tier(value: object) -> int:
    try:
        tier = int(value)
    except (TypeError, ValueError):
        tier = 3
    return tier if tier >= 3 else 3


def resolve_source_tier(*, source_name: object = "", source_url: object = "", configured_tier: object = None) -> int:
    """Return effective authority tier; an unverified URL cannot inherit name authority."""
    name = _clean(source_name)
    host = _host(source_url)
    if host:
        if _domain_match(host, _TIER1_DOMAIN_MARKERS):
            return 1
        if _domain_match(host, _TIER2_DOMAIN_MARKERS):
            return 2
        return _configured_tier(configured_tier)
    if _name_match(name, _TIER1_NAME_MARKERS):
        return 1
    if _name_match(name, _TIER2_NAME_MARKERS):
        return 2
    return _configured_tier(configured_tier)


def resolve_google_news_tier(source_name: object, source_url: object = "") -> int:
    """Google News results are Tier-1/2 only when publisher identity proves it."""
    return resolve_source_tier(source_name=source_name, source_url=source_url, configured_tier=3)


__all__ = ["resolve_source_tier", "resolve_google_news_tier"]
