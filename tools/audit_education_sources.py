from __future__ import annotations

import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / "config" / "education_curriculum.yaml"
FALLBACKS = ROOT / "config" / "education_source_fallbacks.yaml"
EMERGING = ROOT / "config" / "emerging_terminology.yaml"
REPORT = ROOT / "data" / "education_source_audit.json"
MIN_CURRENT_YEAR = 2025
AUDIT_WORKERS = 12
MAINTAINED_CURRENT_DOMAINS = {
    "developers.google.com", "ai.google.dev", "cloud.google.com",
    "huggingface.co", "platform.openai.com", "openai.com",
    "anthropic.com", "docs.anthropic.com", "modelcontextprotocol.io",
    "learn.microsoft.com", "nvidia.com", "docs.nvidia.com",
    "quantum.cloud.ibm.com", "ibm.com", "hai.stanford.edu",
    "nist.gov", "csrc.nist.gov", "airc.nist.gov",
}
TIER1 = {
    "nist.gov", "csrc.nist.gov", "airc.nist.gov", "oecd.org", "iso.org",
    "iec.ch", "ieee.org", "hai.stanford.edu",
}
ORG_ALIASES = {
    "developers.google.com": "google", "ai.google.dev": "google", "cloud.google.com": "google",
    "openai.com": "openai", "platform.openai.com": "openai",
    "anthropic.com": "anthropic", "docs.anthropic.com": "anthropic",
    "arxiv.org": "arxiv", "huggingface.co": "huggingface",
    "learn.microsoft.com": "microsoft", "nvidia.com": "nvidia", "docs.nvidia.com": "nvidia",
    "quantum.cloud.ibm.com": "ibm", "ibm.com": "ibm",
    "modelcontextprotocol.io": "mcp", "hai.stanford.edu": "stanford",
}


def host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def top_domain(h: str) -> str:
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


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
    if h in TIER1 or top_domain(h) in TIER1:
        return 1
    if h.endswith(".edu") or h == "arxiv.org":
        return 2
    if h in {"developers.google.com", "ai.google.dev", "cloud.google.com", "platform.openai.com", "openai.com", "anthropic.com", "docs.anthropic.com"}:
        return 3
    return 4


def is_maintained_domain(url: str) -> bool:
    h = host(url)
    return h in MAINTAINED_CURRENT_DOMAINS or any(h.endswith("." + d) for d in MAINTAINED_CURRENT_DOMAINS)


def extract_year(text: str) -> int | None:
    years: list[int] = []
    patterns = [
        r'"datePublished"\s*:\s*"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
        r'"dateModified"\s*:\s*"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
        r'"dateCreated"\s*:\s*"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
        r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|article:modified_time|citation_date|date|publishdate|last-modified)["\'][^>]+content=["\']([^"\']+)',
        r'(?:published|publication|updated|modified|reviewed|last updated)\D{0,80}(20\d{2})',
        r"/(20\d{2})/\d{1,2}/",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            value = match.group(1)
            year_match = re.search(r"20\d{2}", value)
            if year_match:
                years.append(int(year_match.group(0)))
    return max(years) if years else None


def fetch_source(url: str) -> tuple[bool, int | None, str, bool]:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "AI-Future-Tech-Radar/education-source-audit"})
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return False, None, f"unsupported_content_type:{content_type}", False
        body = r.text[:2_000_000]
        detected_year = extract_year(body)
        maintained_current = bool(is_maintained_domain(url) and not detected_year)
        return True, detected_year, "ok", maintained_current
    except requests.RequestException as exc:
        return False, None, f"request_error:{type(exc).__name__}", False


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_fallbacks() -> dict[str, list[dict]]:
    raw = load_yaml(FALLBACKS).get("education_source_fallbacks", {})
    return {str(key): list(value or []) for key, value in raw.items()}


def collect() -> list[dict]:
    curriculum = load_yaml(CURRICULUM).get("education", {})
    fallbacks = load_fallbacks()
    emerging = load_yaml(EMERGING).get("emerging_terminology", {})
    lessons = list(curriculum.get("lessons") or []) + list(emerging.get("lessons") or [])
    source_specs: list[tuple[dict, str, dict]] = []
    for lesson in lessons:
        lid = str(lesson.get("id"))
        sources = list(lesson.get("sources") or []) + list(fallbacks.get(lid, []) or [])
        seen: set[str] = set()
        for src in sources:
            url = str(src.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            source_specs.append((lesson, lid, src))

    fetched: dict[str, tuple[bool, int | None, str, bool]] = {}
    urls = sorted({str(src.get("url", "")).strip() for _, _, src in source_specs if str(src.get("url", "")).strip()})
    with ThreadPoolExecutor(max_workers=AUDIT_WORKERS) as executor:
        futures = {executor.submit(fetch_source, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                fetched[url] = future.result()
            except Exception as exc:
                fetched[url] = (False, None, f"audit_worker_error:{type(exc).__name__}", False)

    rows: list[dict] = []
    for lesson, lid, src in source_specs:
        url = str(src.get("url", "")).strip()
        ok, detected_year, status, maintained_current = fetched[url]
        declared = src.get("year")
        declared_year = int(declared) if str(declared or "").isdigit() else None
        current = bool(ok and ((detected_year and detected_year >= MIN_CURRENT_YEAR) or maintained_current))
        rows.append({
            "lesson_id": int(lesson.get("id", 0) or 0),
            "lesson_title": lesson.get("title", ""),
            "url": url,
            "host": host(url),
            "organization": organization(url),
            "authority_tier": authority_tier(url),
            "reachable": ok,
            "declared_year": declared_year,
            "detected_year": detected_year,
            "maintained_current": maintained_current,
            "current_2025_plus": current,
            "date_verification": "verified" if detected_year else ("maintained_current" if maintained_current else "unverified"),
            "status": status,
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    by_lesson: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_lesson[row["lesson_id"]].append(row)
    lessons = []
    for lid, items in sorted(by_lesson.items()):
        current = [x for x in items if x["reachable"] and x["current_2025_plus"]]
        orgs = {x["organization"] for x in current}
        authoritative = any(x["authority_tier"] == 1 for x in current)
        warnings = []
        violations = []
        if not current:
            violations.append("no_verified_current_source")
        elif len(current) < 2:
            violations.append("less_than_two_verified_current_sources")
        if len(orgs) < 2 and len(current) >= 2:
            violations.append("sources_not_independent_by_organization")
        if not authoritative:
            warnings.append("no_tier1_authoritative_source_detected")
        if any(x["reachable"] and x["detected_year"] and x["detected_year"] < MIN_CURRENT_YEAR for x in items):
            warnings.append("older_sources_present")
        if any(x["reachable"] and not x["detected_year"] and not x["maintained_current"] for x in items):
            warnings.append("date_unverifiable_for_non_maintained_source")
        lessons.append({
            "lesson_id": lid,
            "lesson_title": items[0]["lesson_title"],
            "verified_current_count": len(current),
            "independent_organizations": sorted(orgs),
            "has_tier1": authoritative,
            "violations": violations,
            "warnings": warnings,
        })
    return {
        "policy": {
            "min_current_year": MIN_CURRENT_YEAR,
            "min_verified_current_sources": 2,
            "require_independent_organizations": True,
            "tier1_is_preferred_not_automatically_blocking": True,
            "maintained_official_docs_can_be_current_without_embedded_year": True,
            "declared_year_alone_never_verifies": True,
            "live_audit_workers": AUDIT_WORKERS,
        },
        "lessons": lessons,
        "source_rows": rows,
        "violation_count": sum(bool(x["violations"]) for x in lessons),
        "warning_count": sum(len(x["warnings"]) for x in lessons),
    }


def main() -> int:
    result = summarize(collect())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [x for x in result["lessons"] if x["violations"]]
    print(f"Education source audit: lessons={len(result['lessons'])} violations={len(bad)} warnings={result['warning_count']}")
    for item in bad:
        print(f"LESSON {item['lesson_id']}: {', '.join(item['violations'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
