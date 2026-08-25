"""Production gate that prevents headlines from drifting away from evidence."""
from __future__ import annotations

import json
import re
from collections import Counter

from education_editor import normalize_editorial_text
from llm_router_light import call_llm_with_fallback, get_quality_chain
from src.editorial_quality_policy import editorial_fields_ok, headline_quality_ok, persian_ratio

_GROUNDING_THRESHOLD = 0.70

_GROUNDING_PROMPT = """تو ویراستار کنترل کیفیت یک رسانه تخصصی فناوری هستی.
فقط بررسی کن آیا «عنوان» درباره همان موضوع اصلی «خلاصه» و «متن منبع» است یا نه.
عنوان نباید موضوعی مستقل، شخص/محصول/نتیجه‌ای متفاوت، یا ادعایی فراتر از متن معرفی کند.
اگر عنوان با شواهد هم‌موضوع است grounded=true و در غیر این صورت grounded=false.
خروجی فقط JSON معتبر به شکل {{"grounded":true}} یا {{"grounded":false}}.

عنوان: {title}

خلاصه: {summary}

متن منبع: {source}
"""

_REPAIR_PROMPT = """عنوان زیر با محتوای منبع هم‌خوان نیست. فقط بر اساس «خلاصه» یک تیتر فارسی حرفه‌ای و دقیق بساز.
هیچ واقعیت جدیدی اضافه نکن. نام رسمی افراد، شرکت‌ها، محصولات و مدل‌ها را Latin نگه دار.
تیتر باید دقیقاً همان موضوع اصلی خلاصه را بیان کند و از موضوعات حاشیه‌ای یا ادعاهای جدید پرهیز کند.
خروجی فقط JSON معتبر با کلید title باشد.

عنوان فعلی: {title}
خلاصه: {summary}
متن منبع: {source}
"""

_TOKEN_RE = re.compile(r"[A-Za-z0-9_./+#:-]+|[\u0600-\u06FF]+")
_STOP = {
    "این", "آن", "برای", "با", "در", "از", "به", "که", "و", "یا", "یک", "های", "هایِ",
    "the", "and", "for", "with", "from", "this", "that", "into", "about", "will", "are", "is",
}


def _tokens(text: str) -> list[str]:
    return [t.lower().strip("._/:;,-") for t in _TOKEN_RE.findall(text or "") if len(t) >= 3 and t.lower() not in _STOP]


def deterministic_grounding_score(title: str, summary: str, source: str) -> float:
    title_tokens = set(_tokens(title))
    evidence = _tokens(" ".join((summary or "", source or "")))
    evidence_counts = Counter(evidence)
    if not title_tokens or not evidence:
        return 0.0
    overlap = sum(1 for token in title_tokens if token in evidence_counts)
    return overlap / max(1, len(title_tokens))


def _llm_grounded(title: str, summary: str, source: str) -> bool | None:
    prompt = _GROUNDING_PROMPT.format(title=title, summary=summary[:2500], source=source[:3500])
    try:
        raw, _provider = call_llm_with_fallback(
            prompt,
            json.dumps({"title": title, "summary": summary[:2500], "source": source[:3500]}, ensure_ascii=False),
            providers=get_quality_chain(),
        )
        data = json.loads(raw or "{}")
        if isinstance(data, dict) and isinstance(data.get("grounded"), bool):
            return bool(data["grounded"])
    except Exception:
        return None
    return None


def _fallback_title(summary: str, item: dict) -> str | None:
    value = normalize_editorial_text(str(summary or "").strip())
    sentences = [s.strip(" .!؟") for s in re.split(r"(?<=[.!؟])\s+", value) if s.strip()]
    if not sentences:
        return None
    candidate = sentences[0]
    if len(candidate) > 150:
        candidate = candidate[:150].rsplit(" ", 1)[0].rstrip("،,:;-")
    if not headline_quality_ok(candidate):
        return None
    if persian_ratio(candidate) < 0.25:
        return None
    if not editorial_fields_ok(candidate, summary, str(item.get("why_it_matters", ""))):
        return None
    return candidate


def ensure_headline_grounding(data: dict, item: dict) -> dict | None:
    """Validate title↔evidence coherence and repair only the headline when needed."""
    if not isinstance(data, dict):
        return None
    title = normalize_editorial_text(str(data.get("title", "")).strip())
    summary = normalize_editorial_text(str(data.get("summary", "")).strip())
    source = normalize_editorial_text(str(item.get("summary", "") or "").strip())
    if not title or not summary:
        return None

    score = deterministic_grounding_score(title, summary, source)
    if score >= _GROUNDING_THRESHOLD:
        data["title_grounding_score"] = round(score, 3)
        return data

    grounded = _llm_grounded(title, summary, source)
    if grounded is True:
        data["title_grounding_score"] = round(score, 3)
        data["title_grounding_verified"] = True
        return data

    prompt = _REPAIR_PROMPT.format(title=title, summary=summary[:2500], source=source[:3500])
    try:
        raw, provider = call_llm_with_fallback(
            prompt,
            json.dumps({"title": title, "summary": summary, "source": source}, ensure_ascii=False),
            providers=get_quality_chain(),
        )
        repaired = json.loads(raw or "{}")
        candidate_title = normalize_editorial_text(str(repaired.get("title", "")).strip())[:160]
        candidate = dict(data)
        candidate["title"] = candidate_title
        repaired_score = deterministic_grounding_score(candidate_title, summary, source)
        if headline_quality_ok(candidate_title) and editorial_fields_ok(candidate_title, summary, str(data.get("why_it_matters", ""))) and repaired_score >= _GROUNDING_THRESHOLD:
            candidate["title_grounding_score"] = round(repaired_score, 3)
            candidate["title_grounding_repaired"] = True
            candidate["_title_grounding_provider"] = provider
            print(f"[Headline Grounding] repaired score={repaired_score:.2f}", flush=True)
            return candidate
    except Exception:
        pass

    fallback = _fallback_title(summary, item)
    if fallback:
        candidate = dict(data)
        candidate["title"] = fallback
        candidate["title_grounding_score"] = round(deterministic_grounding_score(fallback, summary, source), 3)
        candidate["title_grounding_repaired"] = True
        print("[Headline Grounding] deterministic summary-derived title recovery", flush=True)
        return candidate

    print(f"[Headline Grounding] blocked title score={score:.2f}", flush=True)
    return None
