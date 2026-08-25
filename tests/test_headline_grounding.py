from src.headline_grounding import deterministic_grounding_score, ensure_headline_grounding


def test_related_headline_has_strong_evidence_overlap():
    title = "مدل هوش مصنوعی MIT شبیه‌سازی فیزیک را سریع‌تر می‌کند"
    summary = "محققان MIT یک مدل هوش مصنوعی توسعه داده‌اند که می‌تواند شبیه‌سازی‌های فیزیک را با سرعت بیشتری انجام دهد."
    assert deterministic_grounding_score(title, summary, summary) >= 0.55


def test_unrelated_headline_is_not_grounded():
    title = "Sam Altman: AGI سال آینده همه‌چیز را تغییر می‌دهد"
    summary = "محققان MIT یک مدل هوش مصنوعی برای تسریع شبیه‌سازی‌های فیزیک معرفی کرده‌اند و نتایج اولیه آن امیدوارکننده است."
    assert deterministic_grounding_score(title, summary, summary) < 0.55


def test_unrelated_headline_is_replaced_from_summary_when_repair_unavailable(monkeypatch):
    data = {
        "title": "Sam Altman: AGI سال آینده همه‌چیز را تغییر می‌دهد",
        "summary": "محققان MIT یک مدل هوش مصنوعی برای تسریع شبیه‌سازی‌های فیزیک معرفی کرده‌اند.",
        "why_it_matters": "این روش می‌تواند زمان محاسبات فیزیک را کاهش دهد و استفاده از شبیه‌سازی را در پژوهش‌های علمی آسان‌تر کند.",
    }
    item = {"summary": data["summary"]}
    monkeypatch.setattr("src.headline_grounding._llm_grounded", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        "src.headline_grounding.call_llm_with_fallback",
        lambda *args, **kwargs: ('{"title":"نامرتبط"}', "test"),
    )

    grounded = ensure_headline_grounding(data, item)
    assert grounded is not None
    assert grounded["title"] == "محققان MIT یک مدل هوش مصنوعی برای تسریع شبیه‌سازی‌های فیزیک معرفی کرده‌اند"
    assert grounded.get("title_grounding_repaired") is True


def test_grounded_headline_is_preserved():
    data = {
        "title": "مدل هوش مصنوعی MIT شبیه‌سازی فیزیک را سریع‌تر می‌کند",
        "summary": "محققان MIT یک مدل هوش مصنوعی توسعه داده‌اند که می‌تواند شبیه‌سازی‌های فیزیک را با سرعت بیشتری انجام دهد.",
        "why_it_matters": "این روش می‌تواند زمان محاسبات فیزیک را کاهش دهد و پژوهش‌های علمی را سریع‌تر کند.",
    }
    item = {"summary": data["summary"]}
    grounded = ensure_headline_grounding(data, item)
    assert grounded is data
    assert grounded["title"] == data["title"]
    assert grounded["title_grounding_score"] >= 0.55
