"""Evidence-safe Persian summary with bounded editorial QA."""
import json
import os
from llm_router_light import call_llm_with_fallback, get_quality_chain
from education_editor import normalize_editorial_text, news_terminology_review_prompt
from src.editorial_quality_policy import editorial_fields_ok, length_ok, news_language_ok, persian_ratio

_DEPTH={"ai":"محتوای محوری کانال است؛ مدل، روش، عدد، قابلیت، محدودیت و پیامد فنی را دقیق حفظ کن.","quantum":"فقط ارتباط واقعی با AI را برجسته کن؛ از ادعاهای عمومی کوانتومی پرهیز کن.","genetics":"فقط کاربرد مستقیم AI در ژنوم، پروتئین، دارو یا زیست‌محاسبات را پوشش بده.","mind":"فقط AI/AGI/ماشین‌آگاهی/علوم شناختی مرتبط با AI را پوشش بده.","future":"فقط آینده AI، AGI، حکمرانی، اقتصاد یا ریسک‌های مستقیم AI را پوشش بده."}
_PROMPT="""تو تحلیلگر ارشد فارسی‌زبان یک رسانه تخصصی فناوری هستی.
{depth}
قواعد سخت: متن خروجی باید واقعاً فارسی حرفه‌ای باشد؛ نام رسمی افراد، شرکت‌ها، محصولات، مدل‌ها و پروژه‌ها Latin بماند؛ آوانویسی فارسی نام خاص ممنوع؛ key_quote فقط نقل‌قول لفظ‌به‌لفظ کوتاه از متن ورودی باشد و در غیر این صورت خالی؛ summary باید 2 تا 4 جمله کامل و اطلاعات مهم منبع را حفظ کند؛ why_it_matters باید 2 تا 3 جمله کامل و معمولاً 220 تا 360 نویسه باشد؛ حدس یا ادعای جدید ممنوع؛ کوتاه‌نویسی یک‌جمله‌ای ممنوع مگر منبع واقعاً کوتاه باشد.
خروجی دقیقاً JSON: {{"title":"...","summary":"...","why_it_matters":"...","speakers":"","key_quote":"","category":"ai|quantum|genetics|mind|future"}}"""

def _extract_json(raw):
    text=(raw or "").strip()
    if text.startswith("```"):
        text="\n".join(text.splitlines()[1:-1]).strip()
    try: data=json.loads(text)
    except json.JSONDecodeError:
        start,end=text.find("{"),text.rfind("}")
        if start<0 or end<=start: raise
        data=json.loads(text[start:end+1])
    if isinstance(data,dict): return data
    if isinstance(data,list) and data and isinstance(data[0],dict): return data[0]
    raise TypeError(f"Expected JSON object, got {type(data).__name__}")

def _normalize(data,item):
    if not isinstance(data,dict): raise TypeError("summary must be an object")
    data["category"]=item.get("category","ai")
    data["title"]=normalize_editorial_text(str(data.get("title",item.get("title","")))[:160].strip())
    data["summary"]=normalize_editorial_text(str(data.get("summary","")).strip())
    data["why_it_matters"]=normalize_editorial_text(str(data.get("why_it_matters","")).strip())
    data["speakers"]=normalize_editorial_text(str(data.get("speakers","")).strip())
    data["key_quote"]=normalize_editorial_text(str(data.get("key_quote","")).strip()[:240])
    source_text=str(item.get("summary","") or "")
    if data["key_quote"] and data["key_quote"] not in source_text: data["key_quote"]=""
    return data

def _language_ok(data):
    title=str(data.get("title","")); summary=str(data.get("summary","")); why=str(data.get("why_it_matters",""))
    return bool(title.strip() and summary.strip() and why.strip() and news_language_ok(title,summary,why) and editorial_fields_ok(title,summary,why))

def _length_ok(data,source_text):
    return length_ok(str(data.get("summary","")),str(data.get("why_it_matters","")),source_text)

def _editorial_review(data):
    original=dict(data)
    raw,provider=call_llm_with_fallback(news_terminology_review_prompt(),json.dumps(data,ensure_ascii=False),providers=get_quality_chain())
    try:
        reviewed=_extract_json(raw or "")
        if not isinstance(reviewed,dict): return original,None
        candidate=dict(original)
        for key in ("title","summary","why_it_matters","speakers","key_quote","category"):
            if key in reviewed: candidate[key]=str(reviewed[key] or "").strip()
        candidate=_normalize(candidate,{"category":original.get("category","ai"),"title":original.get("title","")})
        if not _language_ok(candidate):
            print("[Editorial QA] reviewer rewrite rejected; preserving validated Persian draft",flush=True)
            return original,None
        return candidate,provider
    except (json.JSONDecodeError,TypeError,ValueError):
        return original,None

def summarize_item(item):
    category=item.get("category","ai")
    prompt=_PROMPT.format(depth=_DEPTH.get(category,_DEPTH["ai"]))
    raw_text=str(item.get("summary","")).strip()
    user=(f"عنوان: {item.get('title','')}\nمنبع: {item.get('source','')}\nنوع: {item.get('content_type','news')}\nشخص کلیدی: {item.get('leader') or item.get('watch_person') or ''}\nمتن: {raw_text[:3500]}")
    raw,provider=call_llm_with_fallback(prompt,user,providers=get_quality_chain())
    if not raw: return None
    try:
        final=_normalize(_extract_json(raw),item)
    except (json.JSONDecodeError,TypeError,ValueError) as exc:
        print(f"[WARN] Summary JSON invalid: {exc}",flush=True); return None
    if _language_ok(final) and _length_ok(final,raw_text):
        if os.getenv("AI_RADAR_EDITORIAL_REVIEW","0").strip().lower() in {"1","true","yes"}:
            final,editorial_provider=_editorial_review(final)
        else:
            editorial_provider=None
    else:
        editorial_provider=None
    final=_normalize(final,item)
    if not _language_ok(final):
        print("[Language Gate] non-educational translation rejected: " f"ratios title={persian_ratio(final.get('title','')):.2f} summary={persian_ratio(final.get('summary','')):.2f} why={persian_ratio(final.get('why_it_matters','')):.2f}",flush=True)
        return None
    if not _length_ok(final,raw_text):
        print(f"[Length Gate] rejected terse summary summary={len(final.get('summary',''))} why={len(final.get('why_it_matters',''))} source={len(raw_text)}",flush=True)
        return None
    final["_provider"]=provider; final["_provider_draft"]=provider; final["_provider_editorial"]=editorial_provider
    return final
