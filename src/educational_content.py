"""Source-grounded Persian educational content for AI Future Tech Radar."""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any

import requests
import yaml

from education_editor import normalize_education_item, terminology_review_prompt
from educational_telegram_style import format_educational_post
from llm_router_light import call_llm_with_fallback, get_quality_chain

ROOT = Path(__file__).resolve().parent.parent
CURRICULUM_PATH = ROOT / "config" / "education_curriculum.yaml"
EMERGING_PATH = ROOT / "config" / "emerging_terminology.yaml"
SOURCE_FALLBACKS_PATH = ROOT / "config" / "education_source_fallbacks.yaml"
STATE_PATH = ROOT / "data" / "education_state.json"
MIN_SOURCE_YEAR = 2025
RLM = "\u200f"

LESSON_15_CURRENT_SOURCES = [
    {
        "name": "NIST: Lessons Learned from the Consortium — Tool Use in Agent Systems",
        "url": "https://www.nist.gov/news-events/news/2025/08/lessons-learned-consortium-tool-use-agent-systems",
        "year": 2025,
    },
    {
        "name": "Google Developers: What's new with Agents: ADK, Agent Engine, and A2A Enhancements",
        "url": "https://developers.googleblog.com/en/agents-adk-agent-engine-a2a-enhancements-google-io/",
        "year": 2025,
    },
]


def _default_state():
    return {"version": 5, "next_lesson": 1, "next_slot": 0, "completed": [], "updated_at": 0}


def load_state():
    if not STATE_PATH.exists():
        return _default_state()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        base = _default_state()
        base.update(data)
        base["completed"] = list(base.get("completed") or [])
        return base if isinstance(data, dict) else _default_state()
    except (OSError, json.JSONDecodeError):
        return _default_state()


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = int(time.time())
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)


def load_curriculum():
    with CURRICULUM_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_emerging():
    if not EMERGING_PATH.exists():
        return {}
    with EMERGING_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_source_fallbacks() -> dict[str, list[dict[str, Any]]]:
    if not SOURCE_FALLBACKS_PATH.exists():
        return {}
    try:
        with SOURCE_FALLBACKS_PATH.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        mapping = raw.get("education_source_fallbacks") or {}
        return {str(k): list(v or []) for k, v in mapping.items()}
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        return {}


def _base_lessons():
    return list(load_curriculum().get("education", {}).get("lessons") or [])


def _emerging_lessons():
    data = load_emerging().get("emerging_terminology", {})
    return list(data.get("lessons") or []) if data.get("enabled", True) else []


def _lesson_sequence():
    base, emerging = _base_lessons(), _emerging_lessons()
    sequence = [("foundation", lesson) for lesson in base]
    sequence.extend(("emerging", lesson) for lesson in emerging)
    return sequence


def _next_lesson():
    sequence = _lesson_sequence()
    if not sequence:
        return None, 0, 0
    state = load_state()
    completed = {int(x) for x in (state.get("completed") or []) if str(x).lstrip("-").isdigit()}
    slot = int(state.get("next_slot", 0) or 0)
    for idx, (track, lesson) in enumerate(sequence):
        lesson_id = int(lesson.get("id", 0) or 0)
        if lesson_id not in completed:
            slot = idx
            break
    else:
        slot = min(max(slot, 0), len(sequence) - 1)
    track, lesson = sequence[slot]
    return lesson, int(lesson.get("id", 0)), len(sequence)


def _extract_source_year(raw_html: str) -> int | None:
    """Extract publication year without mistaking unrelated page dates for it."""
    structured_patterns = [
        r'"datePublished"\s*:\s*"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
        r'"dateModified"\s*:\s*"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
        r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|date|publishdate)["\'][^>]+content=["\'](20\d{2})[-/]\d{1,2}[-/]\d{1,2}',
    ]
    for pattern in structured_patterns:
        match = re.search(pattern, raw_html, flags=re.I)
        if match:
            return int(match.group(1))

    patterns = [
        r"(?:last\s+updated|updated)\s*[:\-]?\s*(20\d{2})[-/]\d{1,2}[-/]\d{1,2}",
        r"(?:published|publication|approved)\s*[:\-]?\s*(20\d{2})[-/]\d{1,2}[-/]\d{1,2}",
        r"(?:published|publication|approved)\s+[^\d]{0,40}(20\d{2})",
        r"/(20\d{2})/\d{1,2}/",
        r"(20\d{2})[-/]\d{1,2}[-/]\d{1,2}",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_html, flags=re.I)
        if match:
            return int(match.group(1))
    return None


def _fetch_reference(url):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "AI-Future-Tech-Radar/education-source-check"})
        r.raise_for_status()
        if "text/html" not in r.headers.get("content-type", ""):
            return "", None
        raw_html = r.text
        year = _extract_source_year(raw_html)
        text = raw_html
        low = text.lower()
        for token in ("<script", "<style", "<nav", "<footer"):
            while token in low:
                start = low.find(token)
                end = low.find("</", start)
                if start < 0 or end < 0:
                    break
                text = text[:start] + text[end:]
                low = text.lower()
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
        return text[:5000], year
    except Exception as exc:
        print(f"[Education] reference fetch skipped: {url} | {exc}", flush=True)
        return "", None


def _parse_json(raw, keys):
    try:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1]).strip()
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start:end + 1] if start >= 0 and end > start else text)
        return {k: str(data[k]).strip() for k in keys} if isinstance(data, dict) and all(str(data.get(k, "")).strip() for k in keys) else None
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"[Education] generated JSON invalid: {exc}", flush=True)
        return None


def _source_candidates(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    lesson_id = str(int(lesson.get("id", 0) or 0))
    candidates = list(lesson.get("sources") or [])
    candidates.extend(load_source_fallbacks().get(lesson_id, []))
    if int(lesson.get("id", 0) or 0) == 15:
        candidates.extend(LESSON_15_CURRENT_SOURCES)

    deduped = []
    seen = set()
    for source in candidates:
        url = str(source.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(dict(source))
    return deduped


def _generate(lesson):
    a, b = lesson["a"], lesson["b"]
    status = str(lesson.get("status", "established"))
    sources = _source_candidates(lesson)
    source_blocks = []
    verified_sources = []
    for source in sources:
        url = str(source.get("url", "")).strip()
        excerpt, detected_year = _fetch_reference(url)
        declared_year = source.get("year")
        year = int(declared_year) if str(declared_year or "").isdigit() else detected_year
        if year is None or year < MIN_SOURCE_YEAR:
            print(f"[Education Source Gate] rejected year={year} url={url}", flush=True)
            continue
        verified_sources.append({**source, "year": year})
        source_blocks.append(f"منبع: {source.get('name')}\nسال: {year}\nURL: {url}\n" + (f"بخش بازیابی‌شده: {excerpt[:2200]}" if excerpt else "مرجع تأیید شد؛ متن صفحه در این اجرا بازیابی نشد."))

    if not verified_sources:
        print(f"[Education Source Gate] FAILED lesson={lesson.get('id')} no verified source >= {MIN_SOURCE_YEAR}", flush=True)
        return None, []

    prompt = f"""تو ویراستار و نویسنده ارشد یک کانال آموزشی فارسی درباره هوش مصنوعی و فناوری هستی.
قواعد سخت و غیرقابل مذاکره:
1) دقیقاً فقط دو مفهوم اصلی را آموزش بده.
2) متن اصلی فارسی، روان، دقیق و ساده باشد.
3) برای مفاهیم پایه، English را حذف کن مگر برای فهم یا شناسایی دقیق واقعاً ضروری باشد.
4) برای اصطلاحات نوظهور، نام رسمی انگلیسی فقط در عنوان همان اصطلاح مجاز است؛ توضیح کاملاً فارسی باشد.
5) نام افراد، شرکت‌ها و محصولات غیرایرانی رسمی و انگلیسی باشند.
6) هیچ آوانویسی فارسی برای اصطلاح تخصصی یا نام خاص نساز.
7) تعریف علمی باید فقط بر اساس seed و منابع تأییدشده 2025 به بعد باشد.
8) هیچ منبع، ادعا، عدد یا تاریخ قبل از 2025 وارد نکن.
9) رابطه، مثال و نکته باید با تعریف‌ها سازگار باشند.
10) خروجی فقط JSON معتبر باشد.
JSON: {{"term_a_definition":"...","term_a_simple":"...","term_b_definition":"...","term_b_simple":"...","relationship":"...","example":"...","takeaway":"..."}}
"""
    user = (f"درس {lesson.get('id')}: {lesson.get('title')}\nوضعیت: {status}\n"
            f"مفهوم اول: {a['term']} / معادل فارسی: {a['fa']}\nتعریف پایه: {a['seed']}\n"
            f"مفهوم دوم: {b['term']} / معادل فارسی: {b['fa']}\nتعریف پایه: {b['seed']}\n"
            f"رابطه پایه: {lesson.get('relation', '')}\n\n" + "\n\n".join(source_blocks))
    raw, provider = call_llm_with_fallback(prompt, user, providers=get_quality_chain())
    keys = ("term_a_definition", "term_a_simple", "term_b_definition", "term_b_simple", "relationship", "example", "takeaway")
    data = _parse_json(raw or "", keys) if raw else None
    if not data:
        return None, verified_sources
    reviewed_raw, reviewed_provider = call_llm_with_fallback(terminology_review_prompt(), json.dumps({"draft": data, "term_a": a["term"], "term_b": b["term"], "status": status}, ensure_ascii=False), providers=get_quality_chain())
    reviewed = _parse_json(reviewed_raw or "", keys) if reviewed_raw else None
    final = normalize_education_item(reviewed or data)
    final["_provider"] = f"{provider or 'AI Future Radar'} + editorial QA"
    if reviewed_provider:
        final["_review_provider"] = reviewed_provider
    return final, verified_sources


def build_educational_item():
    if not load_curriculum().get("education", {}).get("enabled", True):
        return None
    lesson, lesson_id, total = _next_lesson()
    if not lesson:
        return None
    generated, verified_sources = _generate(lesson)
    if not generated:
        raise RuntimeError(f"[Education Contract] no publishable lesson: source policy requires >= {MIN_SOURCE_YEAR}")
    track = "emerging" if lesson_id >= 101 else "foundation"
    return {"content_type": "education", "category": "ai", "education_id": lesson_id, "education_total": total, "education_track": track, "education_track_label": "ترمینولوژی روز و فناوری‌های نو" if track == "emerging" else "مفاهیم پایه و بنیادی", "education_number": lesson_id - 100 if track == "emerging" else lesson_id, "education_status": lesson.get("status", "established"), "education_title": lesson.get("title", ""), "education_term_a": lesson["a"]["term"], "education_term_a_fa": lesson["a"]["fa"], "education_term_b": lesson["b"]["term"], "education_term_b_fa": lesson["b"]["fa"], "education_sources": verified_sources, **generated}


def commit_education_lesson(lesson_id):
    state = load_state()
    completed = [int(x) for x in (state.get("completed") or []) if str(x).lstrip("-").isdigit()]
    if lesson_id not in completed:
        completed.append(int(lesson_id))
    sequence = _lesson_sequence()
    total = len(sequence)
    current_slot = next((idx for idx, (_, lesson) in enumerate(sequence) if int(lesson.get("id", 0)) == int(lesson_id)), 0)
    state["next_slot"] = (current_slot + 1) % total if total else 0
    state["next_lesson"] = int(sequence[state["next_slot"]][1].get("id", 1)) if total else 1
    state["completed"] = completed[-total:] if total else completed
    save_state(state)
