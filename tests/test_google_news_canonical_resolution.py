from types import SimpleNamespace

import scripts.production_with_ranking_audit as prod


def _response(status, *, location="", url="", content_type="text/html"):
    return SimpleNamespace(
        status_code=status,
        headers={"Location": location, "Content-Type": content_type},
        url=url,
        close=lambda: None,
    )


def test_google_news_url_is_resolved_to_publisher(monkeypatch):
    calls = []
    responses = [
        _response(302, location="https://www.example.com/original-story"),
        _response(200, url="https://www.example.com/original-story"),
    ]

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(prod.requests, "get", fake_get)

    item = {
        "title": "Example story",
        "link": "https://news.google.com/rss/articles/example",
    }
    prod._resolve_selected_source_urls([item])

    assert item["link"] == "https://www.example.com/original-story"
    assert item["canonical_url"] == "https://www.example.com/original-story"
    assert item["discovery_link"] == "https://news.google.com/rss/articles/example"
    assert [call[0] for call in calls] == [
        "https://news.google.com/rss/articles/example",
        "https://www.example.com/original-story",
    ]
    assert all(call[1]["allow_redirects"] is False for call in calls)
    assert all(call[1]["stream"] is True for call in calls)


def test_google_news_wrapper_is_not_claimed_resolved_when_redirect_stays_on_google(monkeypatch, capsys):
    def fake_get(url, **kwargs):
        return _response(302, location="https://news.google.com/next-hop")

    monkeypatch.setattr(prod.requests, "get", fake_get)

    item = { "title": "Example story", "link": "https://news.google.com/rss/articles/example" }
    prod._resolve_selected_source_urls([item])
    output = capsys.readouterr().out

    assert item["link"] == "https://news.google.com/rss/articles/example"
    assert "resolved=true" not in output
    assert "attempted=1 resolved=0 unresolved=1" in output


def test_non_google_news_url_is_untouched(monkeypatch):
    def fail_get(*args, **kwargs):
        raise AssertionError("non-Google URLs must not be resolved")

    monkeypatch.setattr(prod.requests, "get", fail_get)

    item = {"title": "Example", "link": "https://example.com/story"}
    prod._resolve_selected_source_urls([item])

    assert item["link"] == "https://example.com/story"
