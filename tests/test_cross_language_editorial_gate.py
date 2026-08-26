from src.editorial_quality_policy import editorial_value_ok


def test_persian_summary_can_pass_against_english_source_with_shared_anchors():
    source = (
        "OpenAI introduced a new reasoning model called GPT-5.6. The model was evaluated on "
        "several benchmarks and improved tool use and coding reliability by 18%. The report "
        "also describes limitations in long-horizon planning and evaluation stability. "
        "Additional experiments compare the model with earlier systems and document failure cases."
    )
    summary = (
        "OpenAI مدل استدلالی جدید GPT-5.6 را معرفی کرده است. این مدل در چند benchmark ارزیابی شده "
        "و در استفاده از ابزار و قابلیت coding حدود 18 درصد بهبود نشان داده است. منبع همچنین "
        "محدودیت‌هایی در برنامه‌ریزی بلندمدت و پایداری ارزیابی گزارش می‌کند."
    )
    why = (
        "وجود بهبود 18 درصدی در استفاده از ابزار می‌تواند برای استقرار عامل‌های هوش مصنوعی اهمیت عملی داشته باشد. "
        "در عین حال، محدودیت برنامه‌ریزی بلندمدت نشان می‌دهد که GPT-5.6 هنوز برای برخی گردش‌کارهای حساس به ارزیابی بیشتر نیاز دارد."
    )
    assert editorial_value_ok("معرفی GPT-5.6", summary, why, source)


def test_generic_persian_copy_still_fails_against_english_source():
    source = (
        "A new AI system achieved 18% higher coding reliability in controlled evaluations and "
        "reported failures in long-horizon planning."
    )
    summary = (
        "این پژوهش پیشرفت مهمی در هوش مصنوعی ایجاد کرده است. این فناوری می‌تواند کاربردهای متنوعی داشته باشد "
        "و مسیر توسعه سامانه‌های آینده را تغییر دهد."
    )
    why = (
        "این پیشرفت می‌تواند برای پژوهش و کاربردهای هوش مصنوعی مهم باشد. پیامدهای آن برای توسعه فناوری "
        "در آینده قابل توجه خواهد بود."
    )
    assert not editorial_value_ok("پیشرفت جدید در هوش مصنوعی", summary, why, source)
