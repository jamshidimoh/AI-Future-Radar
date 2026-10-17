from unittest.mock import Mock

import src.source_evidence as evidence


def _response(status=200, body=b"", headers=None, url="https://publisher.example/story"):
    response = Mock()
    response.status_code = status
    response.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
    response.url = url
    response.encoding = "utf-8"
    response.iter_content.return_value = [body]
    response.close = Mock()
    return response


def test_extracts_article_text_and_skips_navigation_script(monkeypatch):
    html = b"""
    <html><head><title>Publisher Story</title>
    <meta name="description" content="A detailed publisher description."></head>
    <body><nav>Top menu should not appear in source evidence</nav>
    <article><h1>Publisher Story</h1>
    <p>Researchers introduced a new benchmark for evaluating model reasoning under controlled conditions.</p>
    <p>The report describes a set of tests and notes that the evaluation remains limited to the reported tasks.</p>
    <script>Ignore this fake claim about secret results.</script></article></body></html>
    """
    monkeypatch.setattr(evidence.requests, "get", lambda *a, **k: _response(body=html))
    evidence.fetch_article_text.cache_clear()

    text = evidence.fetch_article_text("https://publisher.example/story")

    assert "Publisher page description" in text
    assert "new benchmark for evaluating model reasoning" in text
    assert "Top menu should not appear" not in text
    assert "secret results" not in text


def test_never_fetches_arxiv_or_google_news_wrapper(monkeypatch):
    calls = []
    monkeypatch.setattr(evidence.requests, "get", lambda *a, **k: calls.append(a[0]) or _response())
    evidence.fetch_article_text.cache_clear()

    assert evidence.fetch_article_text("https://arxiv.org/abs/1234.5678") == ""
    assert evidence.fetch_article_text("https://news.google.com/rss/articles/example") == ""
    assert calls == []


def test_google_news_redirect_to_arxiv_is_never_followed(monkeypatch):
    from scripts import production_with_ranking_audit as launcher

    calls = []
    redirect = _response(
        status=302,
        headers={"Location": "https://arxiv.org/abs/2601.01234", "Content-Type": "text/html"},
    )
    monkeypatch.setattr(
        launcher.requests,
        "get",
        lambda url, **kwargs: calls.append((url, kwargs)) or redirect,
    )
    original = "https://news.google.com/rss/articles/example"

    assert launcher._resolve_google_news_url(original) == original
    assert len(calls) == 1
    assert calls[0][0] == original
    assert calls[0][1]["allow_redirects"] is False


def test_redirect_to_excluded_source_is_not_followed(monkeypatch):
    calls = []
    redirect = _response(
        status=302,
        headers={"Location": "https://arxiv.org/abs/2601.01234", "Content-Type": "text/html"},
    )
    monkeypatch.setattr(evidence.requests, "get", lambda url, **kwargs: calls.append(url) or redirect)
    evidence.fetch_article_text.cache_clear()

    assert evidence.fetch_article_text("https://publisher.example/redirect") == ""
    assert calls == ["https://publisher.example/redirect"]


def test_redirect_is_followed_only_after_url_validation(monkeypatch):
    calls = []
    redirect = _response(status=302, headers={"Location": "/article", "Content-Type": "text/html"})
    article = _response(body=b"<html><title>Valid article</title><article><p>This paragraph is long enough to provide a meaningful source excerpt for evidence grounding.</p></article></html>", url="https://publisher.example/article")
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return redirect if len(calls) == 1 else article
    monkeypatch.setattr(evidence.requests, "get", get)
    evidence.fetch_article_text.cache_clear()

    text = evidence.fetch_article_text("https://publisher.example/redirect")

    assert len(calls) == 2
    assert "Valid article" in text
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["timeout"] == (2.5, 3.5)


def test_source_text_does_not_fetch_outside_production_by_default(monkeypatch):
    import src.summarize as summarize

    monkeypatch.delenv("AI_RADAR_SOURCE_EVIDENCE_FETCH", raising=False)
    monkeypatch.delenv("RADAR_PRODUCTION_MODE", raising=False)
    def forbidden_fetch(item):
        raise AssertionError("web fetch should be disabled")
    monkeypatch.setattr(summarize, "article_text_for_item", forbidden_fetch)
    item = {
        "title": "A source-backed summary",
        "summary": "A short RSS snippet.",
        "link": "https://publisher.example/story",
    }

    assert "A short RSS snippet." in summarize._source_text(item)
    assert "_source_article_fetch_attempted" not in item


def test_source_text_uses_extracted_page_evidence_before_short_rss_snippet(monkeypatch):
    import src.summarize as summarize

    monkeypatch.setenv("AI_RADAR_SOURCE_EVIDENCE_FETCH", "1")
    monkeypatch.setattr(
        summarize,
        "article_text_for_item",
        lambda item: "Extracted publisher evidence describes the actual experiment and reports the measured limitations.",
    )
    item = {
        "title": "A machine-learning study",
        "source": "Publisher",
        "summary": "A short feed snippet.",
        "link": "https://publisher.example/story",
    }

    text = summarize._source_text(item)

    assert "Extracted publisher evidence describes the actual experiment" in text
    assert text.index("Extracted publisher evidence") < text.index("A short feed snippet.")
    assert item["_source_article_text"].startswith("Extracted publisher evidence")
