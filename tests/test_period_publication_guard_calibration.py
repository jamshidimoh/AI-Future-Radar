import period_ranked_pipeline as pipeline
from src.publication_guard import _semantic_conflict as publication_semantic_conflict


def _candidate(title="A new AI story", protected=False):
    item = {
        "title": title,
        "summary": "A substantive technology development.",
        "link": "https://example.com/new-story",
    }
    if protected:
        item["protected_content"] = True
        item["leader"] = "Example Leader"
        item["protected_slot"] = True
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


def test_distinct_sam_altman_openai_events_are_not_semantically_conflicted():
    candidate_title = "Sam Altman says OpenAI going public in 2026 would be ‘ill-advised’"
    candidate_summary = "Sam Altman says taking OpenAI public in 2026 would be ill-advised."
    stored_title = "Sam Altman در واشنگتن حضور دارد؛ OpenAI مدل جدیدی از هوش مصنوعی را معرفی می‌کند"
    stored_summary = "Sam Altman در واشنگتن حضور دارد و OpenAI مدل جدیدی از هوش مصنوعی را معرفی می‌کند."
    score = publication_semantic_conflict(candidate_title, candidate_summary, {"title": stored_title, "summary": stored_summary})
    assert score < 0.82
