"""Canonical publisher authority resolution for production provenance.

Query priority and publisher authority are deliberately separate concepts.
A discovery query may be Tier-1 because it targets a monitored person or
organization, but the actual publisher must earn its authority from its
canonical domain/source identity.
"""
from __future__ import annotations

from urllib.parse import urlparse

TIER1_DOMAINS = {
    "openai.com", "www.openai.com", "anthropic.com", "www.anthropic.com",
    "deepmind.google", "www.deepmind.google", "ai.google", "www.ai.google",
    "mit.edu", "www.mit.edu", "news.mit.edu", "csail.mit.edu", "cap.csail.mit.edu",
    "stanford.edu", "hai.stanford.edu", "berkeley.edu", "baulab.us",
    "nature.com", "www.nature.com", "quantamagazine.org", "www.quantamagazine.org",
    "nasa.gov", "www.nasa.gov", "nist.gov", "www.nist.gov", "ieee.org", "www.ieee.org",
    "cmu.edu", "www.cmu.edu", "carnegie-mellon.edu", "www.cmu.edu",
}

TIER2_DOMAINS = {
    "technologyreview.com", "www.technologyreview.com", "spectrum.ieee.org",
    "arstechnica.com", "www.arstechnica.com", "reuters.com", "www.reuters.com",
    "wired.com", "www.wired.com", "scientificamerican.com", "www.scientificamerican.com",
    "newscientist.com", "www.newscientist.com", "theverge.com", "www.theverge.com",
}

TIER3_DOMAINS = {
    "reddit.com", "www.reddit.com", "youtube.com", "www.youtube.com",
    "news.google.com", "x.com", "www.x.com",
}

AGGREGATOR_MARKERS = (
    "google news", "biggo", "news aggregator", "aggregator", "feedly", "yahoo news",
)


def _host(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = urlparse(raw).hostname or ""
    except ValueError:
        host = ""
    return host.lower().lstrip("www.")


def _matches_domain(host: str, domains: set[str]) -> bool:
    host = host.lower().lstrip("www.")
    return any(host == d.lstrip("www.") or host.endswith("." + d.lstrip("www.")) for d in domains)


def resolve_publisher_authority(source_title: str = "", source_url: str = "") -> dict:
    """Resolve authority from the actual publisher identity, never from query tier."""
    title = str(source_title or "").strip()
    host = _host(source_url)
    combined = f"{title} {host}".lower()

    if _matches_domain(host, TIER1_DOMAINS):
        tier, label, score = 1, "authoritative_primary_or_institutional", 9.0
    elif _matches_domain(host, TIER2_DOMAINS):
        tier, label, score = 2, "reputable_specialist_or_news", 7.0
    elif _matches_domain(host, TIER3_DOMAINS) or any(marker in combined for marker in AGGREGATOR_MARKERS):
        tier, label, score = 3, "community_or_aggregator", 4.0
    else:
        tier, label, score = 3, "unverified_publisher", 3.0

    return {
        "publisher_host": host,
        "publisher_title": title,
        "publisher_authority_tier": tier,
        "publisher_authority_label": label,
        "publisher_authority_score": score,
        "publisher_authority_verified": bool(host),
    }
