from src.summarize import _length_ok


def test_long_source_requires_rich_summary():
    data = {"summary": "کوتاه", "why_it_matters": "کوتاه"}
    assert not _length_ok(data, "x" * 1000)


def test_rich_summary_passes_length_gate():
    data = {"summary": "الف" * 260, "why_it_matters": "ب" * 180}
    assert _length_ok(data, "x" * 1000)
