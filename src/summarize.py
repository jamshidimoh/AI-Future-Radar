"""Evidence-safe Persian summary with bounded editorial QA."""
import json
import os
import re

from llm_router_light import call_llm_with_fallback, get_quality_chain
from education_editor import normalize_editorial_text, news_terminology_review_prompt
from src.editorial_quality_policy import editorial_fields_ok, length_ok, news_language_ok, persian_ratio

_DEPTH = {
    "ai": "محتوای محوری کانال است؛ مدل، روش، عدد، قابلیت، محدودیت و پیامد فنی را دقیق حفظ کن.",
    "quantum": "فقط ارتباط واقعی با AI را برجسته کن؛ از ادعاهای عمومی کوانتومی پرهیز کن.",
    "genetics": "فقط کاربرد مستقیم AI در ژنوم، پروتئین، دارو یا زیست‌محاسبات را پوشش بده.",
    "mind": "فقط AI/AGI/ماشین‌آگاهی/علوم شناختی مرتبط با AI را پوشش بده.",
    "future": "فقط آینده AI، AGI، حکمرانی، اقتصاد یا ریسک‌های مستقیم AI را پوشش بده.",
}

_PROMPT = """تو تحلیلگر ارشد فارسی‌زبان یک رسانه تخصصی فناوری هستی.
{depth}
قواعد سخت: متن خروجی باید واقعاً فارسی حرفه‌ای باشد؛ نام رسمی افراد، شرکت‌ها، محصولات، مدل‌ها و پروژه‌ها Latin بماند؛ آوانویسی فارسی نام خاص ممنوع؛ key_quote فقط نقل‌قول لفظ‌به‌لفظ کوتاه از متن ورودی باشد و در غیر این صورت خالی؛ summary باید 3 تا 5 جمله کامل و اطلاعات مهم منبع را حفظ کند و تا حد ممکن جزئیات فنی، شواهد، اعداد، روش یا محدودیت‌های موجود در منبع را فشرده اما معنادار منتقل کند؛ why_it_matters باید 3 تا 4 جمله کامل و معمولاً 320 تا 500 نویسه باشد و مشخصاً پیامد، کاربرد، محدودیت یا اهمیت واقعی خبر را فقط بر پایه شواهد منبع توضیح دهد؛ از تکرار summary خودداری کن؛ حدس یا ادعای جدید ممنوع؛ کوتاه‌نویسی یک‌جمله‌ای ممنوع مگر منبع واقعاً کوتاه باشد.
برای عنوان، حتماً یک تیتر فارسی حرفه‌ای تولید کن و نام رسمی محصولات/افراد/شرکت‌ها را فقط به صورت Latin نگه دار.
خروجی دقیقاً JSON: {{"title":"...","summary":"...","why_it_matters":"...","speakers":"","key_quote":"","category":"ai|quantum|genetics|mind|future"}}"""

_TITLE_REPAIR_PROMPT = """عنوان زیر را برای انتشار در یک رسانه تخصصی فارسی، بدون افزودن ادعای جدید، به یک تیتر کوتاه و حرفه‌ای فارسی تبدیل کن.
نام رسمی افراد، شرکت‌ها، محصولات و مدل‌ها را Latin نگه دار. معنای عنوان را حفظ کن. خروجی فقط JSON معتبر با کلید title باشد.
عنوان: {title}
خلاصه منبع: {summary}"""

_DRAFT_REPAIR_PROMPT = """پیش‌نویس زیر برای انتشار فارسی نامعتبر است. آن را از نو و کامل بازنویسی کن؛ فقط از شواهد موجود در منبع استفاده کن و هیچ ادعای جدیدی نساز.
تمام سه فیلد title، summary و why_it_matters باید فارسی حرفه‌ای باشند. نام رسمی افراد، شرکت‌ها، محصولات، مدل‌ها و پروژه‌ها را Latin نگه دار و آوانویسی فارسی نام خاص انجام نده.
summary باید 3 تا 5 جمله کامل و اطلاعات مهم منبع را حفظ کند و why_it_matters باید 3 تا 4 جمله کامل و معمولاً 320 تا 500 نویسه باشد. why_it_matters باید از summary تکراری نباشد و پیامد، کاربرد، محدودیت یا اهمیت واقعی را فقط بر پایه شواهد منبع بیان کند. key_quote فقط نقل‌قول لفظ‌به‌لفظ کوتاه از متن منبع باشد و در غیر این صورت خالی. category را از مقدار فعلی حفظ کن.
خروجی دقیقاً JSON معتبر با کلیدهای title, summary, why_it_matters, speakers, key_quote, category باشد.

پیش‌نویس: {draft}

متن منبع: {source}"""


def _extract_json(raw):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    raise TypeError(f"Expected JSON object, got {type(data).__name__}")


def _normalize(data, item):
    if not isinstance(data, dict):
        raise TypeError("summary must be an object")
    data["category"] = item.get("category", "ai")
    data["title"] = normalize_editorial_text(str(data.get("title", item.get("title", "")))[:160].strip())
    data["summary"] = normalize_editorial_text(str(data.get("summary", "")).strip())
    data["why_it_matters"] = normalize_editorial_text(str(data.get("why_it_matters", "")).strip())
    data["speakers"] = normalize_editorial_text(str(data.get("speakers", "")).strip())
    data["key_quote"] = normalize_editorial_text(str(data.get("key_quote", "")).strip()[:240])
    source_text = str(item.get("summary", "") or "")
    if data["key_quote"] and data["key_quote"] not in source_text:
        data["key_quote"] = ""
    return data


def _language_ok(data):
    title = str(data.get("title", ""))
    summary = str(data.get("summary", ""))
    why = str(data.get("why_it_matters", ""))
    return bool(
        title.strip()
        and summary.strip()
        and why.strip()
        and news_language_ok(title, summary, why)
        and editorial_fields_ok(title, summary, why)
    )


def _length_ok(data, source_text):
    return length_ok(str(data.get("summary", "")), str(data.get("why_it_matters", "")), source_text)


def _fallback_title_from_persian_summary(data):
    """Provider-independent title recovery when all translation models are unavailable."""
    summary = normalize_editorial_text(str(data.get("summary", "")).strip())
    if persian_ratio(summary) < 0.45:
        return None
    sentences = [x.strip() for x in re.split(r"(?<=[.!؟])\s+", summary) if x.strip()]
    candidate = sentences[0] if sentences else summary
    candidate = re.sub(r"\s+", " ", candidate).strip(" .!؟")
    if len(candidate) > 120:
        candidate = candidate[:120].rsplit(" ", 1)[0].rstrip("،,:;-") + "…"
    if persian_ratio(candidate) < 0.35:
        return None
    repaired = dict(data)
    repaired["title"] = candidate
    if not editorial_fields_ok(candidate, repaired.get("summary", ""), repaired.get("why_it_matters", "")):
        return None
    print(f"[Title Language Recovery] deterministic fallback ratio={persian_ratio(candidate):.2f}", flush=True)
    return repaired


def _repair_title(data):
    title = str(data.get("title", "")).strip()
    summary = str(data.get("summary", "")).strip()
    if not title or persian_ratio(title) >= 0.35:
        return data, None

    prompt = _TITLE_REPAIR_PROMPT.format(title=title, summary=summary[:2500])
    raw, provider = call_llm_with_fallback(
        prompt,
        json.dumps({"title": title, "summary": summary}, ensure_ascii=False),
        providers=get_quality_chain(),
    )
    try:
        repaired = _extract_json(raw or "")
        candidate = dict(data)
        new_title = normalize_editorial_text(str(repaired.get("title", "")).strip())[:160]
        candidate["title"] = new_title
        if persian_ratio(new_title) >= 0.35 and editorial_fields_ok(
            new_title, candidate.get("summary", ""), candidate.get("why_it_matters", "")
        ):
            print(f"[Title Language Recovery] repaired title ratio={persian_ratio(new_title):.2f}", flush=True)
            return candidate, provider
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    fallback = _fallback_title_from_persian_summary(data)
    if fallback is not None:
        return fallback, provider

    print(f"[Title Language Recovery] unable to repair title ratio={persian_ratio(title):.2f}", flush=True)
    return data, provider


def _repair_persian_draft(data, item):
    """Recover the complete Persian editorial draft before the final language gate.

    Title-only recovery cannot rescue a provider that returned an otherwise
    valid-looking but entirely non-Persian draft. This bounded second pass uses
    the same quality-provider chain and validates the complete draft before it
    is allowed back into the normal publication path.
    """
    prompt = _DRAFT_REPAIR_PROMPT.format(
        draft=json.dumps(data, ensure_ascii=False),
        source=str(item.get("summary", "") or "")[:3500],
    )
    raw, provider = call_llm_with_fallback(
        prompt,
        json.dumps({"draft": data, "source": str(item.get("summary", "") or "")[:3500]}, ensure_ascii=False),
        providers=get_quality_chain(),
    )
    try:
        candidate = _normalize(_extract_json(raw or ""), item)
    except (json.JSONDecodeError, TypeError, ValueError):
        print("[Draft Language Recovery] invalid JSON; preserving original draft", flush=True)
        return data, provider

    if _language_ok(candidate):
        if _length_ok(candidate, str(item.get("summary", "") or "")):
            print(
                "[Draft Language Recovery] recovered full Persian draft "
                f"title={persian_ratio(candidate.get('title','')):.2f} "
                f"summary={persian_ratio(candidate.get('summary','')):.2f} "
                f"why={persian_ratio(candidate.get('why_it_matters','')):.2f}",
                flush=True,
            )
        else:
            print("[Draft Language Recovery] recovered Persian draft; deferred length validation to final gate", flush=True)
        return candidate, provider

    print(
        "[Draft Language Recovery] rejected recovered draft "
        f"ratios title={persian_ratio(candidate.get('title','')):.2f} "
        f"summary={persian_ratio(candidate.get('summary','')):.2f} "
        f"why={persian_ratio(candidate.get('why_it_matters','')):.2f}",
        flush=True,
    )
    return data, provider


def _editorial_review(data):
    original = dict(data)
    raw, provider = call_llm_with_fallback(
        news_terminology_review_prompt(),
        json.dumps(data, ensure_ascii=False),
        providers=get_quality_chain(),
    )
    try:
        reviewed = _extract_json(raw or "")
        if not isinstance(reviewed, dict):
            return original, None
        candidate = dict(original)
        for key in ("title", "summary", "why_it_matters", "speakers", "key_quote", "category"):
            if key in reviewed:
                candidate[key] = str(reviewed[key] or "").strip()
        candidate = _normalize(candidate, {"category": original.get("category", "ai"), "title": original.get("title", "")})
        if not _language_ok(candidate):
            print("[Editorial QA] reviewer rewrite rejected; preserving validated Persian draft", flush=True)
            return original, None
        return candidate, provider
    except (json.JSONDecodeError, TypeError, ValueError):
        return original, None


def summarize_item(item):
    category = item.get("category", "ai")
    prompt = _PROMPT.format(depth=_DEPTH.get(category, _DEPTH["ai"]))
    raw_text = str(item.get("summary", "")).strip()
    user = (
        f"عنوان: {item.get('title','')}\n"
        f"منبع: {item.get('source','')}\n"
        f"نوع: {item.get('content_type','news')}\n"
        f"شخص کلیدی: {item.get('leader') or item.get('watch_person') or ''}\n"
        f"متن: {raw_text[:3500]}"
    )
    raw, provider = call_llm_with_fallback(prompt, user, providers=get_quality_chain())
    if not raw:
        return None
    try:
        final = _normalize(_extract_json(raw), item)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"[WARN] Summary JSON invalid: {exc}", flush=True)
        return None

    editorial_provider = None
    if _language_ok(final) and _length_ok(final, raw_text):
        if os.getenv("AI_RADAR_EDITORIAL_REVIEW", "0").strip().lower() in {"1", "true", "yes"}:
            final, editorial_provider = _editorial_review(final)
    else:
        if not _language_ok(final):
            final, recovery_provider = _repair_persian_draft(final, item)
            provider = provider or recovery_provider
        if not _language_ok(final) or not _length_ok(final, raw_text):
            final, recovery_provider = _repair_title(final)
            provider = provider or recovery_provider

    final = _normalize(final, item)
    if not _language_ok(final):
        print(
            "[Language Gate] non-educational translation rejected: "
            f"ratios title={persian_ratio(final.get('title','')):.2f} "
            f"summary={persian_ratio(final.get('summary','')):.2f} "
            f"why={persian_ratio(final.get('why_it_matters','')):.2f}",
            flush=True,
        )
        return None
    if not _length_ok(final, raw_text):
        print(
            f"[Length Gate] rejected terse summary summary={len(final.get('summary',''))} "
            f"why={len(final.get('why_it_matters',''))} source={len(raw_text)}",
            flush=True,
        )
        return None

    final["_provider"] = provider
    final["_provider_draft"] = provider
    final["_provider_editorial"] = editorial_provider
    return final
