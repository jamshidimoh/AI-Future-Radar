"""Deterministic editorial guardrails for Persian AI education and news."""
from __future__ import annotations

import re
from typing import Any

NON_IRANIAN_NAMES_EN = {
    "دمیس هاسابیس": "Demis Hassabis", "جفری هینتون": "Geoffrey Hinton", "یان لوکان": "Yann LeCun", "یان لکون": "Yann LeCun",
    "سم آلتمن": "Sam Altman", "ایلیا سوتسکور": "Ilya Sutskever", "ایلیا سوتسکِوِر": "Ilya Sutskever", "جف دین": "Jeff Dean",
    "اندرو نگ": "Andrew Ng", "اندرو ان جی": "Andrew Ng", "یوئن یوئن آنگ": "Yuen Yuen Ang", "یوئن یوئن انگ": "Yuen Yuen Ang",
}

TECHNICAL_CANONICAL = {
    "هوش مصنوعی مولد": "Generative AI", "هوش مصنوعی زایشی": "Generative AI", "یادگیری ماشین": "Machine Learning", "یادگیری عمیق": "Deep Learning",
    "یادگیری تقویتی": "Reinforcement Learning", "شبکه عصبی مصنوعی": "Artificial Neural Network", "شبکه عصبی": "Neural Network",
    "مدل زبانی بزرگ": "Large Language Model (LLM)", "مدل پایه": "Foundation Model", "پیش‌آموزش": "Pre-training", "ریزتنظیم": "Fine-tuning",
    "فاین‌تیون": "Fine-tuning", "فاین تیون": "Fine-tuning", "استنتاج": "Inference", "توهم‌زایی": "Hallucination", "توهم‌سازی": "Hallucination",
    "بازیابی-تقویت‌شده": "Retrieval-Augmented Generation (RAG)", "بازیابی تقویت‌شده": "Retrieval-Augmented Generation (RAG)", "تعبیه": "Embedding", "بردار تعبیه": "Embedding",
    "توجه": "Attention", "ترنسفورمر": "Transformer", "ابرپارامتر": "Hyperparameter", "پارامتر مدل": "Model Parameter", "پرامپت": "Prompt",
    "مهندسی پرامپت": "Prompt Engineering", "یادگیری در متن": "In-context Learning", "یادگیری درون‌متنی": "In-context Learning",
    "عامل هوش مصنوعی خودمختار": "Autonomous AI Agent", "عامل هوش مصنوعی": "AI Agent", "عاملیت": "Agentic AI", "چندوجهی": "Multimodal",
    "کوانتیزه‌سازی": "Quantization", "توضیح‌پذیری": "Explainability", "مهندسی زمینه": "Context Engineering", "مهندسی کانتکست": "Context Engineering",
    "مهندسی حلقه": "Loop Engineering", "لوپ انجینیرینگ": "Loop Engineering", "کدنویسی وایب": "Vibe Coding", "وایب کدینگ": "Vibe Coding",
    "مهندسی عامل‌محور": "Agentic Engineering", "مهندسی هارنس": "Harness Engineering", "فراخوانی ابزار": "Tool Calling", "فراخوانی تابع": "Function Calling",
    "استفاده از رایانه": "Computer Use", "مدل کانتکست پروتکل": "Model Context Protocol (MCP)", "پروتکل مدل کانتکست": "Model Context Protocol (MCP)",
    "پروتکل زمینه مدل": "Model Context Protocol (MCP)", "پلی‌کریسیس": "Polycrisis", "پلی کریسیس": "Polycrisis", "پلی‌تونی‌تی": "Polytunity", "پلی تونی تی": "Polytunity",
    "ابرهوش مصنوعی": "Artificial Superintelligence (ASI)", "هوش عمومی مصنوعی": "Artificial General Intelligence (AGI)", "مدل جهان": "World Model",
    "استفاده از کامپیوتر": "Computer Use", "عامل مرورگر": "Browser Agent", "عامل کدنویسی": "Coding Agent", "زیرعامل": "Sub-agent", "حافظه عاملی": "Agentic Memory",
    "حلقه عامل": "Agentic Loop", "داده مصنوعی": "Synthetic Data", "ارزیابی مدل": "Model Evaluation",
}

# Educational prose is intentionally Persian-first. Only names and genuinely necessary
# emerging terms are canonicalized; common Persian equivalents remain Persian.
EDUCATION_EMERGING = {
    "مهندسی کانتکست": "Context Engineering", "مهندسی زمینه": "Context Engineering", "لوپ انجینیرینگ": "Loop Engineering", "مهندسی حلقه": "Loop Engineering",
    "کدنویسی وایب": "Vibe Coding", "وایب کدینگ": "Vibe Coding", "پروتکل زمینه مدل": "Model Context Protocol (MCP)",
    "پروتکل مدل کانتکست": "Model Context Protocol (MCP)", "مدل کانتکست پروتکل": "Model Context Protocol (MCP)",
    "مهندسی عامل‌محور": "Agentic Engineering", "مهندسی هارنس": "Harness Engineering", "پلی‌کریسیس": "Polycrisis", "پلی کریسیس": "Polycrisis",
    "پلی‌تونی‌تی": "Polytunity", "پلی تونی تی": "Polytunity",
}


def _replace(value: str, mapping: dict[str, str]) -> str:
    for fa, en in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
        value = value.replace(fa, en)
    return value


def normalize_editorial_text(text: str) -> str:
    value = _replace(str(text or ""), NON_IRANIAN_NAMES_EN)
    value = _replace(value, TECHNICAL_CANONICAL)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def normalize_news_editorial_text(text: str) -> str:
    """Normalize published news prose without converting ordinary Persian AI terms to English."""
    value = _replace(str(text or ""), NON_IRANIAN_NAMES_EN)
    news_emerging = {
        "پلی‌کریسیس": "Polycrisis",
        "پلی کریسیس": "Polycrisis",
        "پلی‌تونی‌تی": "Polytunity",
        "پلی تونی تی": "Polytunity",
    }
    value = _replace(value, news_emerging)
    repairs = {
        "هزینهای": "هزینه‌ای",
        "هزینه ای": "هزینه‌ای",
        "زمانبندی": "زمان‌بندی",
        "زمان بندی": "زمان‌بندی",
        "بازرسیهای": "بازرسی‌های",
        "بازرسی های": "بازرسی‌های",
        "داده های": "داده‌های",
        "مدل های": "مدل‌های",
        "شرکت های": "شرکت‌های",
        "نسخه های": "نسخه‌های",
    }
    value = _replace(value, repairs)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\s+([،؛؟!٪])", r"\1", value)
    value = re.sub(r"([،؛؟!٪])(?=[^\s])", r"\1 ", value)
    value = re.sub(r"\.{2,}", "…", value)
    return value.strip()


def normalize_education_text(text: str) -> str:
    """Persian-first normalization for education; do not translate ordinary AI terms."""
    value = _replace(str(text or ""), NON_IRANIAN_NAMES_EN)
    value = _replace(value, EDUCATION_EMERGING)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    fields = ("title", "summary", "why_it_matters", "speakers", "key_quote", "term_a_definition", "term_a_simple", "term_b_definition", "term_b_simple", "relationship", "example", "takeaway", "education_title")
    out = dict(item)
    for field in fields:
        if field in out:
            out[field] = normalize_editorial_text(str(out[field]))
    return out


def normalize_education_item(item: dict[str, Any]) -> dict[str, Any]:
    fields = ("term_a_definition", "term_a_simple", "term_b_definition", "term_b_simple", "relationship", "example", "takeaway")
    out = dict(item)
    for field in fields:
        if field in out:
            out[field] = normalize_education_text(str(out[field]))
    return out


def terminology_review_prompt() -> str:
    return """ویرایشگر نهایی زبان و اصطلاحات فنی AI Future Tech Radar هستی.
قواعد اجباری:
1) در محتوای آموزشی، فارسی اولویت دارد و اصطلاحات پایه را تا حد امکان با معادل فارسی رایج بنویس.
2) English فقط وقتی ضروری است که برای شناسایی دقیق یک اصطلاح، نام خاص یا فهم بهتر لازم باشد.
3) اصطلاحات نوظهور مانند Vibe Coding، Loop Engineering، Context Engineering، Agentic Engineering و MCP را با املای رسمی انگلیسی بنویس و در صورت نیاز معادل/توضیح فارسی بده.
4) نام افراد غیرایرانی را با نام رسمی Latin script بنویس: Demis Hassabis, Geoffrey Hinton, Yann LeCun, Sam Altman, Ilya Sutskever, Jeff Dean, Andrew Ng, Yuen Yuen Ang.
5) Polycrisis و Polytunity را به صورت انگلیسی نگه دار.
6) فارسی روان، طبیعی، دقیق و قابل‌فهم باشد؛ انگلیسی زائد ممنوع.
7) ادعای جدید یا آوانویسی جدید نساز.
8) خروجی فقط JSON معتبر با همان کلیدهای ورودی باشد.
"""


def news_terminology_review_prompt() -> str:
    return """تو ویراستار ارشد فارسی یک رسانه تخصصی AI و فناوری هستی.
قواعد سخت:
1) زبان پیش‌فرض title، summary و why_it_matters فارسی طبیعی و حرفه‌ای است؛ خروجی نباید شبیه ترجمه ماشینی باشد.
2) مفاهیم رایج را فارسی بنویس: «هوش مصنوعی»، «یادگیری ماشین»، «یادگیری عمیق»، «هوش مصنوعی مولد»، «مدل زبانی بزرگ»، «ارزیابی مدل» و مانند آن. فقط برای اصطلاح نوظهور یا نام دقیق، شکل انگلیسی را در صورت نیاز داخل پرانتز و فقط در نخستین کاربرد بیاور.
3) نام افراد، شرکت‌ها، محصولات و مدل‌های مشخص را با نام رسمی Latin نگه دار؛ از تبدیل بی‌دلیل تمام متن به زنجیره‌ای از واژه‌های انگلیسی خودداری کن.
4) title باید کوتاه، خبری و طبیعی باشد؛ ترجمه لفظ‌به‌لفظ headline انگلیسی ممنوع. از ساختارهای کلیشه‌ای و تحت‌اللفظی پرهیز کن.
5) summary باید دقیقاً بگوید چه اتفاقی افتاده یا چه یافته‌ای منتشر شده است. why_it_matters باید پیامد یا اهمیت مستقل ارائه کند، نه تکرار summary.
6) فعل روشن، نهاد مشخص، جمله‌های متوسط و نیم‌فاصله درست به‌کار ببر. عبارت‌های اداری و ترجمه‌زده مانند «می‌باشد»، «صورت می‌گیرد»، «در این راستا»، «گزارش می‌کند که» و «این موضوع نشان می‌دهد» ممنوع.
7) هیچ ادعای جدید، تفسیر شخصی یا جزئیات خارج از منبع اضافه نکن.
8) نقل‌قول فقط وقتی نگه داشته شود که در متن منبع قابل اتکا باشد؛ در غیر این صورت خالی بماند.
9) خروجی فقط JSON معتبر با کلیدهای title, summary, why_it_matters, speakers, key_quote, category باشد.
"""

