import period_ranked_pipeline as pipeline


def test_global_ranking_returns_top_four_only():
    items = [
        {"title":"A","editorial_score":91,"source":"source-a","content_type":"research"},
        {"title":"B","editorial_score":95,"source":"source-b","content_type":"news"},
        {"title":"C","editorial_score":80,"source":"source-c","content_type":"research"},
        {"title":"D","editorial_score":88,"source":"source-d","content_type":"research"},
        {"title":"E","editorial_score":99,"source":"source-e","content_type":"news"},
    ]
    ranked = pipeline._global_ranked_selection(items, 1, 2, 2, {})
    assert [x["title"] for x in ranked] == ["E","B","A","D"]
    assert [x["period_rank"] for x in ranked] == [1,2,3,4]


def test_protected_leader_is_reserved_and_selected():
    monkeypatch = __import__("pytest").MonkeyPatch()
    try:
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_interview", lambda item: item.get("leader") == "Leader A")
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_activity", lambda item: False)
        monkeypatch.setattr(pipeline._pipeline, "_leader_source_authority", lambda item: 3)
        protected, regular = pipeline._eligibility_split([{"leader":"Leader A","title":"Important interview"},{"title":"Regular story"}], 2)
        assert len(protected) == 1
        assert len(regular) == 1
        assert protected[0]["protected_content"] is True
        assert protected[0]["_rank_is_tier0"] is True
        assert protected[0]["priority_story_people"] == ["Leader A"]
    finally:
        monkeypatch.undo()


def test_protected_leader_enters_tier0_ranking():
    items = [{"leader":"Leader A","protected_content":True,"leader_watch_protected":True,"leader_source_authority":3,"editorial_score":80,"title":"Leader interview"},{"editorial_score":100,"title":"Regular top","source":"source-regular"}]
    ranked = pipeline._global_ranked_selection(items, 1, 2, 2, {})
    assert ranked[0]["title"] == "Leader interview"
    assert ranked[0]["_rank_is_tier0"] is True
    assert ranked[0]["tier0_rank"] == 1


def test_tier0_interview_is_not_blocked_by_semantic_similarity(monkeypatch):
    record = {"title": "Jensen Huang discusses AI infrastructure", "link": "https://example.com/old-interview"}
    candidate = {"title": "Jensen Huang on the future of AI computing", "link": "https://example.com/new-interview", "content_type": "interview", "summary": "Jensen Huang gives a substantive interview about AI infrastructure, accelerated computing, agents, robotics and the future of technology."}
    monkeypatch.setattr(pipeline, "_load_records", lambda: [record])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args, **kwargs: 0.95)
    assert pipeline._exclude_published_candidates([candidate]) == [candidate]


def test_protected_leader_story_bypasses_semantic_history(monkeypatch):
    record = {"title": "Dario Amodei discusses AI safety and model development", "link": "https://example.com/old"}
    candidate = {"title": "Dario Amodei on the next phase of AI safety", "link": "https://example.com/new", "content_type": "interview", "protected_content": True, "leader_watch_protected": True, "summary": "A substantive interview about AI safety, frontier models and deployment risks."}
    monkeypatch.setattr(pipeline, "_load_records", lambda: [record])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args, **kwargs: 0.99)
    assert pipeline._exclude_published_candidates([candidate]) == [candidate]


def test_tier0_exact_url_repeat_is_still_blocked(monkeypatch):
    record = {"title": "Jensen Huang discusses AI infrastructure", "link": "https://example.com/interview"}
    candidate = {"title": "A different title for Jensen Huang", "link": "https://example.com/interview", "content_type": "interview", "summary": "Jensen Huang gives a substantive interview about AI infrastructure and computing."}
    monkeypatch.setattr(pipeline, "_load_records", lambda: [record])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args, **kwargs: 0.95)
    assert pipeline._exclude_published_candidates([candidate]) == []
