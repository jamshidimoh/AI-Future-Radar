"""Source-to-summary grounding gate for production content."""
from __future__ import annotations

import json
from collections import Counter
import re

from llm_router_light import call_llm_with_fallback, get_quality_chain
from education_editor import normalize_editorial_text

_TOKEN_RE = re.compile(r"[A-Za-z0-9_./+#:-]+|[\u0600-\u06FF]+")
_STOP = {"the", "and", "for", "with", "from", "this", "that", "about", "into", "این", "آن", "برای", "با", "در", "از", "به", "که", "و", "یک"}
_THRESHOLD = 0.45
_EVIDENCE_THRESHOLD = 0.15

_CHECK_PROMPT = """تو داور حقیقت‌سنج یک رسانه تخصصی فناوری هستی.
پیش‌نویس زیر را فقط با «عنوان اصلی منبع» و «متن اصلی منبع» مقایسه کن.
اگر summary یا title ادعای مرکزی، شخص، محصول، فناوری، رویداد یا نتیجه‌ای را مطرح می‌کند که در منبع پشتیبانی نمی‌شود، grounded=false.
اشتراک چند واژه به‌تنهایی کافی نیست. تغییر موضوع یا hallucination را رد کن.
اگر همه ادعاهای اصلی پیش‌نویس از منبع قابل پشتیبانی است، grounded=true.
خروجی فقط JSON معتبر: {"grounded":true} یا {"grounded":false}.

عنوان اصلی منبع:
{source_title}

متن اصلی منبع:
{source_text}

پیش‌نویس:
{draft}
"""

_REPAIR_PROMPT = """پیش‌نویس زیر از منبع اصلی منحرف شده است. آن را از نو تولید کن.
فقط اطلاعات صریح یا مستقیماً قابل استنتاج از «عنوان اصلی منبع» و «متن اصلی منبع» را استفاده کن.
هیچ شخص، محصول، عدد، نتیجه، فناوری یا زمینه‌ای را که در منبع نیست اضافه نکن.
عنوان باید موضوع واقعی منبع را بیان کند؛ summary و why_it_matters نیز باید فقط درباره همان موضوع باشند.
خروجی دقیقاً JSON با کلیدهای title, summary, why_it_matters, speakers, key_quote, category باشد.

عنوان اصلی منبع:
{source_title}

متن اصلی منبع:
{source_text}

پیش‌نویس فعلی:
{draft}
"""


def _tokens(text: str) -> set[str]:
    return {t.lower().strip("._/:;,-") for t in _TOKEN_RE.findall(text or "") if len(t) >= 3 and t.lower() not in _STOP}


def deterministic_source_overlap(source_title: str, source_text: str, draft: dict) -> float:
    title_tokens = _tokens(source_title)
    draft_tokens = _tokens(" ".join(str(draft.get(k) or "") for k in ("title", "summary", "why_it_matters")))
    if not title_tokens or not draft_tokens:
        return 0.0
    counts = Counter(draft_tokens)
    return sum(1 for t in title_tokens if t in counts) / max(1, len(title_tokens))


def deterministic_source_evidence_overlap(source_text: str, draft: dict) -> float:
    source_tokens = _tokens(source_text)
    draft_tokens = _tokens(" ".join(str(draft.get(k) or "") for k in ("title", "summary", "why_it_matters")))
    if not source_tokens or not draft_tokens:
        return 0.0
    return len(source_tokens & draft_tokens) / max(1, len(source_tokens))


def _deterministic_anchor_ok(source_title: str, source_text: str, draft: dict) -> bool:
    title_tokens = _tokens(source_title)
    if not title_tokens:
        return False
    title_overlap = deterministic_source_overlap(source_title, source_text, draft)
    evidence_overlap = deterministic_source_evidence_overlap(source_text, draft)
    return title_overlap > 0.0 or evidence_overlap >= _EVIDENCE_THRESHOLD


def _llm_check(source_title: str, source_text: str, draft: dict) -> bool | None:
    prompt = _CHECK_PROMPT.format(source_title=source_title[:500], source_text=source_text[:5000], draft=json.dumps(draft, ensure_ascii=False)[:5000])
    try:
        raw, _provider = call_llm_with_fallback(prompt, json.dumps({"source_title": source_title, "source_text": source_text[:5000], "draft": draft}, ensure_ascii=False), providers=get_quality_chain())
        data = json.loads(raw or "{}")
        if isinstance(data, dict) and isinstance(data.get("grounded"), bool):
            return bool(data["grounded"])
    except Exception:
        return None
    return None


def _repair(source_title: str, source_text: str, draft: dict) -> dict | None:
    prompt = _REPAIR_PROMPT.format(source_title=source_title[:500], source_text=source_text[:5000], draft=json.dumps(draft, ensure_ascii=False)[:5000])
    try:
        raw, _provider = call_llm_with_fallback(prompt, json.dumps({"source_title": source_title, "source_text": source_text[:5000], "draft": draft}, ensure_ascii=False), providers=get_quality_chain())
        value = json.loads(raw or "{}")
        if isinstance(value, dict) and value.get("title") and value.get("summary"):
            return value
    except Exception:
        return None
    return None


def ensure_source_grounding(draft: dict, item: dict) -> dict | None:
    if not isinstance(draft, dict):
        return None
    source_title = normalize_editorial_text(str(item.get("title", "")).strip())
    source_text = normalize_editorial_text(str(item.get("summary", "") or "").strip())
    if not source_title or not source_text:
        return None

    overlap = deterministic_source_overlap(source_title, source_text, draft)
    evidence_overlap = deterministic_source_evidence_overlap(source_text, draft)
    if not _deterministic_anchor_ok(source_title, source_text, draft):
        print(f"[Source Grounding] hard-blocked deterministic topic drift title_overlap={overlap:.2f} evidence_overlap={evidence_overlap:.2f}", flush=True)
        return None

    verdict = _llm_check(source_title, source_text, draft) if overlap < _THRESHOLD else True
    if verdict is True:
        draft["source_grounding_score"] = round(overlap, 3)
        draft["source_grounding_evidence_overlap"] = round(evidence_overlap, 3)
        draft["source_grounding_verified"] = True
        return draft

    repaired = _repair(source_title, source_text, draft)
    if repaired is not None:
        repaired_overlap = deterministic_source_overlap(source_title, source_text, repaired)
        repaired_evidence_overlap = deterministic_source_evidence_overlap(source_text, repaired)
        repaired_verdict = _llm_check(source_title, source_text, repaired)
        if _deterministic_anchor_ok(source_title, source_text, repaired) and (repaired_verdict is True or repaired_overlap >= _THRESHOLD):
            repaired["source_grounding_score"] = round(repaired_overlap, 3)
            repaired["source_grounding_evidence_overlap"] = round(repaired_evidence_overlap, 3)
            repaired["source_grounding_repaired"] = True
            print(f"[Source Grounding] repaired score={repaired_overlap:.2f} evidence_overlap={repaired_evidence_overlap:.2f}", flush=True)
            return repaired

    print(f"[Source Grounding] blocked overlap={overlap:.2f} evidence_overlap={evidence_overlap:.2f}", flush=True)
    return None
