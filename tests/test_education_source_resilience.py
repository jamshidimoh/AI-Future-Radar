import production_resilient_runner as runner


def test_stanford_2026_canonical_url_gets_year_override(monkeypatch):
    monkeypatch.setattr(runner, "_ORIGINAL_FETCH_REFERENCE", lambda url: ("Stanford AI Index 2026", None))
    excerpt, year = runner._fetch_reference_with_canonical_year("https://hai.stanford.edu/ai-index/2026-ai-index-report")
    assert excerpt
    assert year == 2026


def test_noncanonical_url_does_not_get_generic_url_year_guess(monkeypatch):
    monkeypatch.setattr(runner, "_ORIGINAL_FETCH_REFERENCE", lambda url: ("content", None))
    _, year = runner._fetch_reference_with_canonical_year("https://example.com/reports/2026-ai-index-report")
    assert year is None
