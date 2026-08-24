import json
from unittest.mock import patch

import summarize


def test_title_recovery_repairs_valid_persian_title_without_changing_body():
    item = {
        "category": "ai",
        "title": "AI in Context, produced by 80,000 Hours",
        "summary": "یک خلاصه فارسی معتبر درباره یک تحول مهم در هوش مصنوعی که شواهد منبع را حفظ می‌کند.",
        "why_it_matters": "این تحول برای مسیر توسعه و استفاده از هوش مصنوعی مهم است و پیامدهای فنی و راهبردی قابل توجهی دارد.",
    }
    repaired_payload = json.dumps({"title": "هوش مصنوعی در زمینه؛ برنامه 80,000 Hours"}, ensure_ascii=False)
    with patch.object(summarize, "call_llm_with_fallback", return_value=(repaired_payload, "test-provider")):
        repaired, provider = summarize._repair_title(item)

    assert repaired["title"] != item["title"]
    assert summarize.persian_ratio(repaired["title"]) >= 0.25
    assert repaired["summary"] == item["summary"]
    assert repaired["why_it_matters"] == item["why_it_matters"]
    assert provider == "test-provider"
