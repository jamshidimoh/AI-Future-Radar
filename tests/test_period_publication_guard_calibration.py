import period_ranked_pipeline as pipeline


def _candidate(title="A new AI story", protected=False):
    item = {
        "title": title,
        "summary": "A substantive technology development.",
        "link": "https://example.com/new-story",
    }
    if protected:
        item["protected_content"] = True
        item["protected_slot"] = True
        item["leader_watch_protected"] = True
        item["leader"] = "Example Leader"
    return item


def test_regular_topic_similarity_below_same_story_threshold_is_not_blocked(monkeypatch):
    monkeypatch.setattr(pipeline, "_load_records", lambda: [{"title": "Older related story", "link": "https://example.com/old"}])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args: 0.70)

    result = pipeline._exclude_published_candidates([_candidate()])

    assert len(result) == 1


def test_regular_high_confidence_semantic_identity_is_blocked(monkeypatch):
    monkeypatch.setattr(pipeline, "_load_records", lambda: [{"title": "Older same story", "link": "https://example.com/old"}])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args: 0.90)

    result = pipeline._exclude_published_candidates([_candidate()])

    assert result == []


def test_protected_story_ignores_broad_semantic_similarity(monkeypatch):
    monkeypatch.setattr(pipeline, "_load_records", lambda: [{"title": "Related leader story", "leader": "Example Leader", "link": "https://example.com/old"}])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args: 0.99)
    monkeypatch.setattr(pipeline, "probable_same_story", lambda *args: False)

    result = pipeline._exclude_published_candidates([_candidate(protected=True)])

    assert len(result) == 1


def test_protected_same_story_rewrite_is_blocked(monkeypatch):
    monkeypatch.setattr(pipeline, "_load_records", lambda: [{"title": "Same leader story", "leader": "Example Leader", "link": "https://example.com/old"}])
    monkeypatch.setattr(pipeline, "probable_same_story", lambda *args: True)

    result = pipeline._exclude_published_candidates([_candidate(protected=True)])

    assert result == []
