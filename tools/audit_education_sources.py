from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from education_source_policy import MIN_CURRENT_YEAR, assess_source  # noqa: E402

CURRICULUM = ROOT / "config" / "education_curriculum.yaml"
MODULES = ROOT / "config" / "education_curriculum_modules.yaml"
FALLBACKS = ROOT / "config" / "education_source_fallbacks.yaml"
EMERGING = ROOT / "config" / "emerging_terminology.yaml"
REPORT = ROOT / "data" / "education_source_audit.json"
AUDIT_WORKERS = 12


def host(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


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
            year_match = re.search(r"20\d{2}", match.group(1))
            if year_match:
                years.append(int(year_match.group(0)))
    return max(years) if years else None


def fetch_source(url: str) -> tuple[bool, int | None, str]:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "AI-Future-Tech-Radar/education-source-audit"})
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


def load_fallbacks() -> dict[str, list[dict]]:
    raw = load_yaml(FALLBACKS).get("education_source_fallbacks", {})
    return {str(key): list(value or []) for key, value in raw.items()}


def collect() -> list[dict]:
    curriculum = load_yaml(CURRICULUM).get("education", {})
    modules = load_yaml(MODULES).get("education_curriculum_modules", {})
    fallbacks = load_fallbacks()
    emerging = load_yaml(EMERGING).get("emerging_terminology", {})
    lessons = list(curriculum.get("lessons") or []) + list(modules.get("lessons") or []) + list(emerging.get("lessons") or [])
    source_specs: list[tuple[dict, dict]] = []
    for lesson in lessons:
        lid = str(lesson.get("id"))
        sources = list(lesson.get("sources") or []) + list(fallbacks.get(lid, []) or [])
        seen: set[str] = set()
        for src in sources:
            url = str(src.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            source_specs.append((lesson, src))

    fetched: dict[str, tuple[bool, int | None, str]] = {}
    urls = sorted({str(src.get("url", "")).strip() for _, src in source_specs if str(src.get("url", "")).strip()})
    with ThreadPoolExecutor(max_workers=AUDIT_WORKERS) as executor:
        futures = {executor.submit(fetch_source, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                fetched[url] = future.result()
            except Exception as exc:
                fetched[url] = (False, None, f"audit_worker_error:{type(exc).__name__}")

    rows: list[dict] = []
    for lesson, src in source_specs:
        url = str(src.get("url", "")).strip()
        ok, detected_year, status = fetched[url]
        declared = src.get("year")
        declared_year = int(declared) if str(declared or "").isdigit() else None
        assessment = assess_source(url=url, reachable=ok, detected_year=detected_year, declared_year=declared_year)
        rows.append({
            "lesson_id": int(lesson.get("id", 0) or 0),
            "lesson_title": lesson.get("title", ""),
            "domain": lesson.get("domain", ""),
            "url": url,
            "host": host(url),
            "organization": assessment["organization"],
            "authority_tier": assessment["authority_tier"],
            "authority_score": assessment["authority_score"],
            "reachable": ok,
            "declared_year": declared_year,
            "detected_year": detected_year,
            "maintained_current": assessment.get("status") == "maintained_current",
            "current_2025_plus": bool(assessment.get("current")),
            "date_verification": "verified" if detected_year else ("maintained_current" if assessment.get("current") else "unverified"),
            "status": assessment.get("status", status),
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
        authoritative = any(int(x.get("authority_tier", 4)) == 1 for x in current)
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
            "domain": items[0].get("domain", ""),
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
        "lesson_count": len(lessons),
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
