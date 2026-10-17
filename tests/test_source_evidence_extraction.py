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


def test_extraction_prefers_article_body_over_related_story_cards(monkeypatch):
    html = b"""
    <html><head><title>Primary Research Article</title></head><body>
    <main>
      <article>
        <h1>Primary Research Article</h1>
        <p>The researchers report a new method for measuring model calibration under controlled conditions with independently evaluated test data.</p>
        <p>The study describes the evaluation protocol, its results, and limitations in the tested settings.</p>
      </article>
    </main>
    <div class="related-content">
      <h3>Unrelated related story about a different company</h3>
      <p>This recommended story describes a separate experiment, different organizations, and unrelated numerical findings that must not be treated as evidence for the main article.</p>
    </div>
    </body></html>
    """
    monkeypatch.setattr(evidence.requests, "get", lambda *a, **k: _response(body=html))
    evidence.fetch_article_text.cache_clear()

    text = evidence.fetch_article_text("https://publisher.example/primary")

    assert "new method for measuring model calibration" in text
    assert "Unrelated related story" not in text
    assert "separate experiment" not in text


def test_short_semantic_article_beats_long_related_story_outside_main(monkeypatch):
    html = b"""
    <html><head><title>Primary Article</title></head><body>
    <main><article>
      <h1>Primary Article</h1>
      <p>The study reports a new calibration method and its evaluation limits.</p>
    </article></main>
    <div class="related-content">
      <p>This unrelated recommended story describes a different organization, a separate benchmark, several unrelated experimental findings, and a distinct future product roadmap that must not be treated as source evidence for the primary article.</p>
    </div>
    </body></html>
    """
    monkeypatch.setattr(evidence.requests, "get", lambda *a, **k: _response(body=html))
    evidence.fetch_article_text.cache_clear()

    text = evidence.fetch_article_text("https://publisher.example/short-primary")

    assert "calibration method and its evaluation limits" in text
    assert "unrelated recommended story" not in text
    assert "future product roadmap" not in text


def test_article_element_outranks_related_cards_inside_main(monkeypatch):
    html = b"""
    <html><head><title>Primary Article</title></head><body>
    <main>
      <article>
        <h1>Primary Article</h1>
        <p>The study describes a calibrated neural model, a controlled evaluation protocol, and a limitation tied to the reported benchmark.</p>
      </article>
      <aside class="related-content">
        <h3>Unrelated recommended story</h3>
        <p>This longer related story names a different company and reports unrelated experiments, separate numerical results, and a different product roadmap. It must not contaminate the primary article's evidence even though the card sits inside the main element.</p>
      </aside>
    </main>
    </body></html>
    """
    monkeypatch.setattr(evidence.requests, "get", lambda *a, **k: _response(body=html))
    evidence.fetch_article_text.cache_clear()

    text = evidence.fetch_article_text("https://publisher.example/main-with-related-card")

    assert "controlled evaluation protocol" in text
    assert "Unrelated recommended story" not in text
    assert "different product roadmap" not in text


def test_extraction_falls_back_to_body_paragraphs_without_semantic_article_tags(monkeypatch):
    html = b"""
    <html><head><title>Publisher Story</title></head><body>
    <div class="story">
      <p>The publisher describes a newly evaluated neural model and explains the controlled test design used for the experiment.</p>
      <p>The article also notes an explicit limitation: the result applies only to the reported evaluation conditions.</p>
    </div>
    <div class="recommendations"><p>This is an unrelated recommendation card with a separate company and project.</p></div>
    </body></html>
    """
    monkeypatch.setattr(evidence.requests, "get", lambda *a, **k: _response(body=html))
    evidence.fetch_article_text.cache_clear()

    text = evidence.fetch_article_text("https://publisher.example/story-without-main")

    assert "controlled test design" in text
    assert "reported evaluation conditions" in text


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
