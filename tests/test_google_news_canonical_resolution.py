from types import SimpleNamespace

import scripts.production_with_ranking_audit as prod


def test_google_news_url_is_resolved_to_publisher(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(url="https://www.example.com/original-story", close=lambda: None)

    monkeypatch.setattr(prod.requests, "get", fake_get)

    item = {
        "title": "Example story",
        "link": "https://news.google.com/rss/articles/example",
    }
    prod._resolve_selected_source_urls([item])

    assert item["link"] == "https://www.example.com/original-story"
    assert item["canonical_url"] == "https://www.example.com/original-story"
    assert item["discovery_link"] == "https://news.google.com/rss/articles/example"
    assert calls[0][1]["allow_redirects"] is True
    assert calls[0][1]["stream"] is True


def test_non_google_news_url_is_untouched(monkeypatch):
    def fail_get(*args, **kwargs):
        raise AssertionError("non-Google URLs must not be resolved")

    monkeypatch.setattr(prod.requests, "get", fail_get)

    item = {"title": "Example", "link": "https://example.com/story"}
    prod._resolve_selected_source_urls([item])

    assert item["link"] == "https://example.com/story"
