"""Final publication-quality gates for source/entity/language/RTL consistency."""
from __future__ import annotations

import json
import re

import requests

from src.editorial_quality_policy import persian_ratio, terminology_safety_ok
from src.llm_router_light import call_llm_with_fallback, get_quality_chain
from src.rtl_contract import force_rtl_blocks

FETCH_TIMEOUT = 8
BAD_TRANSLATION_PATTERNS = (
    r"m?attention",
    r"قابل\s*attention",
    r"\bAttention\b",
    r"\b(?:the|this|that|and|with|from)\b",
)

_ENTITY_PROMPT = """تو ویراستار نهایی یک رسانه تخصصی فناوری هستی.
عنوان، خلاصه و اطلاعات انتسابی زیر را با متن منبع اصلی مقایسه کن.
تمرکز ویژه روی نام افراد، شرکت‌ها، محصولات و مدل‌هاست.
اگر فرد/شرکت/محصولی به فرد یا موجودیت دیگری نسبت داده شده، grounded=false.
اگر عنوان «مدیرعامل X» است، شخص معرفی‌شده باید واقعاً مدیرعامل X در منبع باشد.
اگر اطلاعات کافی برای تأیید وجود ندارد، grounded=false.
خروجی فقط JSON معتبر: {"grounded":true} یا {"grounded":false}.

عنوان منبع:
{source_title}

متن منبع:
{source_text}

متن منتشرشدنی:
{draft}
"""

_REWRITE_PROMPT = """متن زیر برای انتشار فارسی یک رسانه تخصصی فناوری دارای خطای انتساب یا زبان است.
فقط بر اساس متن منبع اصلی بازنویسی کن.
نام افراد، شرکت‌ها، محصولات و مدل‌ها را دقیقاً مطابق منبع نگه دار.
هیچ عدد، ادعا یا شخص جدیدی اضافه نکن.
همه توضیحات فارسی روان و طبیعی باشند؛ واژه‌های English فقط برای نام خاص یا اصطلاح ضروری.
عبارت‌های خراب مانند Attention، مAttention و ترجمه‌الگویی را حذف کن.
خروجی فقط JSON معتبر با کلیدهای title, summary, why_it_matters, speakers, key_quote, category.

منبع:
{source_text}

متن فعلی:
{draft}
"""

def _bad_language(text: str) -> bool:
    value = str(text or "")
    return any(re.search(pattern, value, re.I) for pattern in BAD_TRANSLATION_PATTERNS)

def _fetch_source(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        r = requests.get(raw, timeout=FETCH_TIMEOUT, allow_redirects=True,
                          headers={"User-Agent": "AI-Future-Radar/1.0"})
        text = r.text or ""
        r.close()
        # Keep enough article text while avoiding giant HTML prompts.
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I|re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I|re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text[:12000]
    except requests.RequestException:
        return ""

def ensure_publication_quality(draft: dict, item: dict) -> dict | None:
    if not isinstance(draft, dict):
        return None
    fields = ("title", "summary", "why_it_matters")
    if not all(str(draft.get(k) or "").strip() for k in fields):
        return None

    combined = " ".join(str(draft.get(k) or "") for k in fields)
    language_bad = _bad_language(combined)
    ratios = [persian_ratio(str(draft.get(k) or "")) for k in fields]
    language_bad = language_bad or ratios[1] < 0.60 or ratios[2] < 0.60
    language_bad = language_bad or any(not terminology_safety_ok(str(draft.get(k) or "")) for k in fields)

    source_url = item.get("link") or item.get("canonical_url") or item.get("url") or ""
    source_text = _fetch_source(source_url)
    entity_check_needed = bool(source_text)

    # Entity verification is mandatory when a canonical source is fetchable.
    if entity_check_needed:
        prompt = _ENTITY_PROMPT.format(
            source_title=str(item.get("title") or "")[:800],
            source_text=source_text[:7000],
            draft=json.dumps(draft, ensure_ascii=False)[:7000],
        )
        try:
            raw, _ = call_llm_with_fallback(
                prompt,
                json.dumps({"source_title": item.get("title"), "source_text": source_text[:7000], "draft": draft}, ensure_ascii=False),
                providers=get_quality_chain(),
            )
            verdict = json.loads(raw or "{}").get("grounded")
        except Exception:
            verdict = False
        if verdict is not True:
            language_bad = True
            draft["_entity_grounding_failed"] = True
            print("[Publication Quality Gate] entity/source attribution mismatch or unverifiable", flush=True)

    if not language_bad:
        draft["_publication_quality_verified"] = True
        return force_rtl_blocks(json.dumps(draft, ensure_ascii=False)) and draft

    if not source_text:
        print("[Publication Quality Gate] blocked: language/entity defect without source evidence", flush=True)
        return None

    prompt = _REWRITE_PROMPT.format(
        source_text=source_text[:8000],
        draft=json.dumps(draft, ensure_ascii=False)[:7000],
    )
    try:
        raw, provider = call_llm_with_fallback(
            prompt,
            json.dumps({"source_text": source_text[:8000], "draft": draft}, ensure_ascii=False),
            providers=get_quality_chain(),
        )
        repaired = json.loads(raw or "{}")
    except Exception as exc:
        print(f"[Publication Quality Gate] repair failed: {type(exc).__name__}", flush=True)
        return None

    if not isinstance(repaired, dict) or not all(str(repaired.get(k) or "").strip() for k in fields):
        return None
    repaired_combined = " ".join(str(repaired.get(k) or "") for k in fields)
    repaired_ratios = [persian_ratio(str(repaired.get(k) or "")) for k in fields]
    if (
        _bad_language(repaired_combined)
        or repaired_ratios[1] < 0.60
        or repaired_ratios[2] < 0.60
        or any(not terminology_safety_ok(str(repaired.get(k) or "")) for k in fields)
    ):
        print("[Publication Quality Gate] repaired text failed language safety", flush=True)
        return None

    verify_prompt = _ENTITY_PROMPT.format(
        source_title=str(item.get("title") or "")[:800],
        source_text=source_text[:7000],
        draft=json.dumps(repaired, ensure_ascii=False)[:7000],
    )
    try:
        raw, _ = call_llm_with_fallback(
            verify_prompt,
            json.dumps({"source_title": item.get("title"), "source_text": source_text[:7000], "draft": repaired}, ensure_ascii=False),
            providers=get_quality_chain(),
        )
        if json.loads(raw or "{}").get("grounded") is not True:
            print("[Publication Quality Gate] repaired entity attribution still failed", flush=True)
            return None
    except Exception:
        return None

    repaired["_publication_quality_repaired"] = True
    repaired["_publication_quality_provider"] = provider or "quality-chain"
    print("[Publication Quality Gate] repaired and verified", flush=True)
    return repaired
