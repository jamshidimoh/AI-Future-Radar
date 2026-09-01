from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one match in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def replace_all(path: Path, old: str, new: str, minimum: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count < minimum:
        raise SystemExit(f"expected at least {minimum} matches in {path}, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# YouTube: retain the real description, but enrich priority long-form channels with
# transcript evidence instead of silently preferring one or the other.
replace_once(
    ROOT / "src" / "fetch_youtube.py",
    '''    raw_summary = str(item.get("summary") or "").strip()\n    transcript = _get_transcript_snippet(video_id) if not raw_summary else ""\n    evidence_text = transcript or raw_summary\n    evidence_source = "transcript" if transcript else ("channel_page_description" if raw_summary else "none")\n''',
    '''    raw_summary = str(item.get("summary") or "").strip()\n    channel_name = str(channel.get("name") or "").strip()\n    priority_transcript = channel_name in {\n        "Lex Fridman Podcast",\n        "Dwarkesh Patel",\n        "No Priors Podcast",\n        "Sean Carroll's Mindscape",\n    }\n    transcript = _get_transcript_snippet(video_id) if priority_transcript and video_id else ""\n    if transcript and raw_summary:\n        evidence_text = f"{raw_summary}\\n\\n[Transcript evidence]\\n{transcript}"\n        evidence_source = "channel_page_description+transcript"\n    else:\n        evidence_text = transcript or raw_summary\n        evidence_source = "transcript" if transcript else ("channel_page_description" if raw_summary else "none")\n''',
)

summarize = ROOT / "src" / "summarize.py"
replace_once(
    summarize,
    '''_VALUE_REPAIR_PROMPT = """تو ویراستار ارشد محتوای یک رسانه تخصصی فناوری هستی. پیش‌نویس زیر از نظر زبان معتبر است اما از نظر ارزش اطلاعاتی ضعیف است.\nفقط با استفاده از متن منبع آن را اصلاح کن.\nsummary: دو تا چهار جمله که مشخصاً بگوید چه اتفاقی افتاده، مهم‌ترین روش/یافته/قابلیت/عدد یا محدودیت چیست. کلی‌گویی و تکرار عنوان ممنوع.\nwhy_it_matters: دو یا سه جمله که یک پیامد مشخص برای پژوهش، محصول، زیرساخت، بازار، ایمنی، حکمرانی یا مسیر آینده فناوری توضیح دهد. از کلیشه‌هایی مانند «این موضوع آینده AI را تغییر می‌دهد» بدون سازوکار مشخص استفاده نکن.\nsummary و why_it_matters نباید یکدیگر را تکرار کنند. هیچ ادعایی خارج از منبع اضافه نکن. نام رسمی افراد، شرکت‌ها، مدل‌ها و پروژه‌ها Latin بماند.\nخروجی فقط JSON معتبر با کلیدهای title, summary, why_it_matters, speakers, key_quote, category باشد.\n\nپیش‌نویس: {draft}\n\nمتن منبع: {source}"""\n''',
    '''_VALUE_REPAIR_PROMPT = """تو ویراستار ارشد محتوای یک رسانه تخصصی فناوری هستی. پیش‌نویس زیر از نظر زبان معتبر است اما از نظر ارزش اطلاعاتی ضعیف است.\nفقط با استفاده از متن منبع آن را اصلاح کن.\nsummary باید 3 تا 5 جمله کامل باشد و مشخصاً بگوید چه اتفاقی افتاده، مهم‌ترین روش/یافته/قابلیت/عدد یا محدودیت چیست. کلی‌گویی و تکرار عنوان ممنوع.\nwhy_it_matters باید 3 تا 4 جمله کامل باشد و یک پیامد مشخص برای پژوهش، محصول، زیرساخت، بازار، ایمنی، حکمرانی یا مسیر آینده فناوری توضیح دهد. از کلیشه‌هایی مانند «این موضوع آینده AI را تغییر می‌دهد» بدون سازوکار مشخص استفاده نکن.\nsummary و why_it_matters نباید یکدیگر را تکرار کنند. هیچ ادعایی خارج از منبع اضافه نکن. جزئیات فنی، اعداد، نام مدل/سیستم و محدودیت‌های صریح منبع را در صورت وجود حفظ کن. نام رسمی افراد، شرکت‌ها، مدل‌ها و پروژه‌ها Latin بماند.\nخروجی فقط JSON معتبر با کلیدهای title, summary, why_it_matters, speakers, key_quote, category باشد.\n\nپیش‌نویس: {draft}\n\nمتن منبع: {source}"""\n''',
)
replace_once(
    summarize,
    '''def _normalize(data, item):\n''',
    '''def _source_text(item, max_chars=3500):\n    """Build the strongest available evidence context without duplicating identical fields."""\n    parts = []\n    seen = set()\n    for key in ("summary", "evidence_text", "description"):\n        value = str(item.get(key, "") or "").strip()\n        if not value or value in seen:\n            continue\n        seen.add(value)\n        parts.append(value)\n    return "\\n\\n".join(parts)[:max_chars]\n\n\ndef _normalize(data, item):\n''',
)
replace_all(
    summarize,
    '''        source=str(item.get("summary", "") or "")[:3500],\n''',
    '''        source=_source_text(item),\n''',
    minimum=2,
)
replace_once(
    summarize,
    '''        json.dumps({"draft": data, "source": str(item.get("summary", "") or "")[:3500]}, ensure_ascii=False),\n''',
    '''        json.dumps({"draft": data, "source": _source_text(item)}, ensure_ascii=False),\n''',
)
replace_once(
    summarize,
    '''    raw_text = str(item.get("summary", "")).strip()\n''',
    '''    raw_text = _source_text(item)\n''',
)

print("PUBLICATION_EVIDENCE_FIX_APPLIED")
# Trigger marker: the temporary runner is intentionally idempotent.
