from __future__ import annotations

import json
import re
from collections import defaultdict
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

TIER1 = {
    "nist.gov", "csrc.nist.gov", "airc.nist.gov", "oecd.org", "iso.org",
    "iec.ch", "ieee.org", "hai.stanford.edu",
}


def host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def top_domain(h: str) -> str:
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


def authority_tier(url: str) -> int:
    h = host(url)
    if h in TIER1 or top_domain(h) in TIER1:
        return 1
    if h.endswith(".edu") or h.endswith("arxiv.org"):
        return 2
    if h in {"developers.google.com", "ai.google.dev", "openai.com", "anthropic.com"}:
        return 3
    return 4


def extract_year(text: str) -> int | None:
    patterns = [
        r'"datePublished"\s*:\s*"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
        r'"dateModified"\s*:\s*"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
        r'(?:published|publication|updated|modified)\D{0,60}(20\d{2})',
        r"/(20\d{2})/\d{1,2}/",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return int(m.group(1))
    return None


def fetch_source(url: str) -> tuple[bool, int | None, str]:
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "AI-Future-Tech-Radar/education-source-audit"})
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return False, None, f"unsupported_content_type:{content_type}"
        return True, extract_year(r.text[:2_000_000]), "ok"
    except requests.RequestException as exc:
        return False, None, f"request_error:{type(exc).__name__}"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def collect() -> list[dict]:
    curriculum = load_yaml(CURRICULUM).get("education", {})
    fallbacks = load_yaml(FALLBACKS).get("education_source_fallbacks", {})
    emerging = load_yaml(EMERGING).get("emerging_terminology", {})
    lessons = list(curriculum.get("lessons") or []) + list(emerging.get("lessons") or [])
    rows: list[dict] = []
    for lesson in lessons:
        lid = str(lesson.get("id"))
        sources = list(lesson.get("sources") or []) + list(fallbacks.get(lid, []) or [])
        seen: set[str] = set()
        for src in sources:
            url = str(src.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            ok, detected_year, status = fetch_source(url)
            declared = src.get("year")
            declared_year = int(declared) if str(declared or "").isdigit() else None
            rows.append({
                "lesson_id": int(lesson.get("id", 0) or 0),
                "lesson_title": lesson.get("title", ""),
                "url": url,
                "host": host(url),
                "authority_tier": authority_tier(url),
                "reachable": ok,
                "declared_year": declared_year,
                "detected_year": detected_year,
                "current_2025_plus": bool(detected_year and detected_year >= MIN_CURRENT_YEAR),
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
        domains = {top_domain(x["host"]) for x in current}
        authoritative = any(x["authority_tier"] == 1 for x in current)
        violations = []
        if not current:
            violations.append("no_verified_current_source")
        if len(current) < 2:
            violations.append("less_than_two_verified_current_sources")
        if len(domains) < 2 and len(current) >= 2:
            violations.append("sources_not_independent_by_domain")
        if not authoritative:
            violations.append("no_tier1_authoritative_source")
        lessons.append({
            "lesson_id": lid,
            "lesson_title": items[0]["lesson_title"],
            "verified_current_count": len(current),
            "independent_domains": sorted(domains),
            "has_tier1": authoritative,
            "violations": violations,
        })
    return {
        "policy": {
            "min_current_year": MIN_CURRENT_YEAR,
            "min_verified_current_sources": 2,
            "require_independent_domains": True,
            "require_tier1_when_available": True,
            "declared_year_alone_never_verifies": True,
        },
        "lessons": lessons,
        "source_rows": rows,
        "violation_count": sum(bool(x["violations"]) for x in lessons),
    }


def main() -> int:
    result = summarize(collect())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [x for x in result["lessons"] if x["violations"]]
    print(f"Education source audit: lessons={len(result['lessons'])} violations={len(bad)}")
    for item in bad:
        print(f"LESSON {item['lesson_id']}: {', '.join(item['violations'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
