"""Shared source-governance policy for Education runtime and audits."""
from __future__ import annotations

from urllib.parse import urlparse

MIN_CURRENT_YEAR = 2025
MIN_INDEPENDENT_CURRENT_SOURCES = 2

MAINTAINED_CURRENT_DOMAINS = {
    "developers.google.com", "ai.google.dev", "cloud.google.com",
    "huggingface.co", "scikit-learn.org", "sbert.net", "pytorch.org",
    "tensorflow.org", "platform.openai.com", "openai.com",
    "anthropic.com", "docs.anthropic.com", "modelcontextprotocol.io",
    "learn.microsoft.com", "nvidia.com", "docs.nvidia.com",
    "quantum.cloud.ibm.com", "ibm.com", "hai.stanford.edu",
    "nist.gov", "csrc.nist.gov", "airc.nist.gov", "oecd.org",
}

TIER1_DOMAINS = {
    "nist.gov", "csrc.nist.gov", "airc.nist.gov", "oecd.org", "iso.org",
    "iec.ch", "ieee.org", "hai.stanford.edu",
}

ORG_ALIASES = {
    "developers.google.com": "google", "ai.google.dev": "google", "cloud.google.com": "google",
    "openai.com": "openai", "platform.openai.com": "openai",
    "anthropic.com": "anthropic", "docs.anthropic.com": "anthropic",
    "arxiv.org": "arxiv", "huggingface.co": "huggingface",
    "scikit-learn.org": "scikit-learn", "sbert.net": "sentence-transformers",
    "pytorch.org": "pytorch", "tensorflow.org": "tensorflow",
    "learn.microsoft.com": "microsoft", "nvidia.com": "nvidia", "docs.nvidia.com": "nvidia",
    "quantum.cloud.ibm.com": "ibm", "ibm.com": "ibm",
    "modelcontextprotocol.io": "mcp", "hai.stanford.edu": "stanford",
}

PRIMARY_DOMAINS = {
    "nist.gov", "csrc.nist.gov", "airc.nist.gov", "developers.google.com", "ai.google.dev",
    "hai.stanford.edu", "oecd.org", "iso.org", "ieee.org", "anthropic.com", "openai.com",
    "deepmind.google", "research.google", "microsoft.com", "ibm.com", "nvidia.com",
}


def host(url: str) -> str:
    return (urlparse(str(url)).hostname or "").lower().removeprefix("www.")


def top_domain(hostname: str) -> str:
    parts = hostname.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname


def organization(url: str) -> str:
    h = host(url)
    if h in ORG_ALIASES:
        return ORG_ALIASES[h]
    if h.endswith(".google.com") or h.endswith(".google.dev"):
        return "google"
    if h.endswith(".nist.gov"):
        return "nist"
    if h.endswith(".stanford.edu"):
        return "stanford"
    if h.endswith(".edu"):
        return h
    return top_domain(h)


def authority_tier(url: str) -> int:
    h = host(url)
    if h in TIER1_DOMAINS or top_domain(h) in TIER1_DOMAINS:
        return 1
    if h.endswith(".edu") or h == "arxiv.org":
        return 2
    if h in PRIMARY_DOMAINS:
        return 3
    return 4


def authority_score(url: str) -> int:
    score = 60
    h = host(url)
    if h in PRIMARY_DOMAINS or top_domain(h) in PRIMARY_DOMAINS:
        score += 30
    if "arxiv.org" in h:
        score += 20
    if any(x in str(url).lower() for x in ("/standard", "/spec", "specification", "recommendation")):
        score += 10
    return min(score, 100)


def is_maintained_current(url: str) -> bool:
    h = host(url)
    return h in MAINTAINED_CURRENT_DOMAINS or any(h.endswith("." + d) for d in MAINTAINED_CURRENT_DOMAINS)


def assess_source(*, url: str, reachable: bool, detected_year: int | None, declared_year: int | None = None) -> dict:
    if not reachable:
        return {"current": False, "status": "unreachable", "organization": organization(url), "authority_tier": authority_tier(url), "authority_score": authority_score(url)}
    if detected_year is not None and detected_year >= MIN_CURRENT_YEAR:
        return {"current": True, "status": "dated_current", "year": detected_year, "organization": organization(url), "authority_tier": authority_tier(url), "authority_score": authority_score(url)}
    if detected_year is not None and detected_year < MIN_CURRENT_YEAR:
        return {"current": False, "status": "outdated", "year": detected_year, "organization": organization(url), "authority_tier": authority_tier(url), "authority_score": authority_score(url)}
    if is_maintained_current(url):
        return {"current": True, "status": "maintained_current", "year": declared_year, "organization": organization(url), "authority_tier": authority_tier(url), "authority_score": authority_score(url)}
    return {"current": False, "status": "date_unverified", "organization": organization(url), "authority_tier": authority_tier(url), "authority_score": authority_score(url)}


def validate_current_sources(sources: list[dict]) -> tuple[bool, list[dict], str]:
    valid = []
    for source in sources:
        if not bool(source.get("current_verified", False)):
            continue
        item = dict(source)
        item.setdefault("organization", organization(item.get("url", "")))
        item.setdefault("authority_tier", authority_tier(item.get("url", "")))
        item.setdefault("authority_score", authority_score(item.get("url", "")))
        valid.append(item)
    orgs = {str(x.get("organization")) for x in valid if x.get("organization")}
    if len(valid) < MIN_INDEPENDENT_CURRENT_SOURCES:
        return False, valid, f"need at least {MIN_INDEPENDENT_CURRENT_SOURCES} current sources"
    if len(orgs) < MIN_INDEPENDENT_CURRENT_SOURCES:
        return False, valid, "current sources are not independent by organization"
    if not any(int(x.get("authority_score", 0)) >= 80 for x in valid):
        return False, valid, "no authoritative current source"
    valid.sort(key=lambda x: (int(x.get("authority_score", 0)), int(x.get("authority_tier", 4))), reverse=True)
    return True, valid, "ok"
