from src.canonical_story import canonical_url, normalize_title, story_id, url_id


def test_tracking_parameters_do_not_change_url_identity():
    a = "https://Example.com/news/story/?utm_source=x&utm_campaign=y"
    b = "https://example.com/news/story"
    assert canonical_url(a) == canonical_url(b)
    assert url_id({"link": a}) == url_id({"link": b})


def test_editorial_prefix_does_not_change_story_identity():
    a = {"title": "Breaking: OpenAI releases a new model"}
    b = {"title": "OpenAI releases a new model"}
    assert normalize_title(a["title"]) == normalize_title(b["title"])
    assert story_id(a) == story_id(b)


def test_different_titles_remain_distinct_exact_identities():
    assert story_id({"title": "OpenAI releases a new model"}) != story_id({"title": "Anthropic releases a new model"})


def test_empty_identity_is_safe():
    assert story_id({"title": ""}) == ""
    assert url_id({"link": ""}) == ""
