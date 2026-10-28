import period_ranked_pipeline as pipeline


def test_global_ranking_returns_top_four_only():
    items = [
        {"title":"A","editorial_score":91,"source":"source-a","content_type":"research","category":"ai"},
        {"title":"B","editorial_score":95,"source":"source-b","content_type":"news","category":"quantum"},
        {"title":"C","editorial_score":80,"source":"source-c","content_type":"research","category":"mind"},
        {"title":"D","editorial_score":88,"source":"source-d","content_type":"research","category":"future"},
        {"title":"E","editorial_score":99,"source":"source-e","content_type":"news","category":"robotics"},
    ]
    ranked = pipeline._global_ranked_selection(items, 1, 2, 2, {})
    titles = [x["title"] for x in ranked]
    assert len(ranked) == 4
    assert titles[0] == "E"
    assert set(titles) == {"A", "B", "D", "E"}
    assert len({x["source"] for x in ranked}) == 4
    assert [x["period_rank"] for x in ranked] == [1,2,3,4]


def test_protected_leader_is_reserved_and_selected():
    monkeypatch = __import__("pytest").MonkeyPatch()
    try:
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_interview", lambda item: item.get("leader") == "Leader A")
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_activity", lambda item: False)
        monkeypatch.setattr(pipeline._pipeline, "_leader_source_authority", lambda item: 3)
        protected, regular = pipeline._eligibility_split([{"leader":"Leader A","title":"Important interview","summary":"Discusses AI agents and frontier models."},{"title":"Regular story"}], 2)
        assert len(protected) == 1
        assert len(regular) == 1
        assert protected[0]["protected_content"] is True
        assert protected[0]["_rank_is_tier0"] is True
        assert protected[0]["priority_story_people"] == ["Leader A"]
    finally:
        monkeypatch.undo()


def test_non_technology_leader_does_not_get_tier0_reservation():
    monkeypatch = __import__("pytest").MonkeyPatch()
    try:
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_interview", lambda item: item.get("leader") == "Leader A")
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_activity", lambda item: False)
        monkeypatch.setattr(pipeline._pipeline, "_leader_source_authority", lambda item: 3)
        protected, regular = pipeline._eligibility_split([
            {"leader":"Leader A","title":"Why gravity is changing our understanding of fundamental physics","summary":"A discussion about fundamental physics and scientific discovery.","content_type":"interview","_ai_link":True},
        ], 2)
        assert protected == []
        assert len(regular) == 1
        assert regular[0]["protected_content"] is False
        assert regular[0]["_rank_is_tier0"] is False
    finally:
        monkeypatch.undo()


def test_protected_leader_with_ai_signal_still_gets_tier0_reservation():
    monkeypatch = __import__("pytest").MonkeyPatch()
    try:
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_interview", lambda item: item.get("leader") == "Leader A")
        monkeypatch.setattr(pipeline._pipeline, "_is_protected_leader_activity", lambda item: False)
        monkeypatch.setattr(pipeline._pipeline, "_leader_source_authority", lambda item: 3)
        protected, regular = pipeline._eligibility_split([
            {"leader":"Leader A","title":"Dario Amodei on the next phase of AI safety","summary":"A substantive interview about frontier models, AI safety and deployment risks.","content_type":"interview"},
        ], 2)
        assert len(protected) == 1
        assert regular == []
        assert protected[0]["protected_content"] is True
        assert protected[0]["_rank_is_tier0"] is True
    finally:
        monkeypatch.undo()


def test_protected_leader_enters_tier0_ranking():
    items = [{"leader":"Leader A","protected_content":True,"leader_watch_protected":True,"leader_source_authority":3,"editorial_score":80,"title":"Leader interview","protected_slot":True},{"editorial_score":100,"title":"Regular top","source":"source-regular"}]
    ranked = pipeline._global_ranked_selection(items, 1, 2, 2, {})
    assert ranked[0]["title"] == "Leader interview"
    assert ranked[0]["_rank_is_tier0"] is True
    assert ranked[0]["tier0_rank"] == 1


def test_tier0_interview_is_not_blocked_by_semantic_similarity(monkeypatch):
    record = {"title": "Jensen Huang discusses AI infrastructure", "link": "https://example.com/old-interview"}
    candidate = {"title": "Jensen Huang on the future of AI computing", "link": "https://example.com/new-interview", "content_type": "interview", "summary": "Jensen Huang gives a substantive interview about AI infrastructure, accelerated computing, agents, robotics and the future of technology.", "protected_slot": True}
    monkeypatch.setattr(pipeline, "_load_records", lambda: [record])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args, **kwargs: 0.95)
    assert pipeline._exclude_published_candidates([candidate]) == [candidate]


def test_protected_leader_story_bypasses_semantic_history(monkeypatch):
    record = {"title": "Dario Amodei discusses AI safety and model development", "link": "https://example.com/old"}
    candidate = {"title": "Dario Amodei on the next phase of AI safety", "link": "https://example.com/new", "content_type": "interview", "protected_content": True, "leader_watch_protected": True, "summary": "A substantive interview about AI safety, frontier models and deployment risks.", "protected_slot": True}
    monkeypatch.setattr(pipeline, "_load_records", lambda: [record])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args, **kwargs: 0.99)
    assert pipeline._exclude_published_candidates([candidate]) == [candidate]


def test_tier0_exact_url_repeat_is_still_blocked(monkeypatch):
    record = {"title": "Jensen Huang discusses AI infrastructure", "link": "https://example.com/interview"}
    candidate = {"title": "A different title for Jensen Huang", "link": "https://example.com/interview", "content_type": "interview", "summary": "Jensen Huang gives a substantive interview about AI infrastructure and computing."}
    monkeypatch.setattr(pipeline, "_load_records", lambda: [record])
    monkeypatch.setattr(pipeline, "_semantic_conflict", lambda *args, **kwargs: 0.95)
    assert pipeline._exclude_published_candidates([candidate]) == []


def test_window_counts_scopes_to_last_n_non_education_items():
    history = [
        {"ts": 1, "source": "MarkTechPost", "category": "ai", "content_type": "research"},
        {"ts": 2, "source": "MarkTechPost", "category": "ai", "content_type": "research"},
        {"ts": 3, "source": "education", "category": "ai", "content_type": "education"},
        {"ts": 4, "source": "Simon Willison", "category": "ai", "content_type": "analysis"},
        {"ts": 5, "source": "Nature", "category": "mind", "content_type": "research"},
    ]
    source_counts, area_counts = pipeline._window_counts(history, window_items=3)
    # Education entries are excluded from the window before slicing, and only the
    # last 3 non-education entries are counted.
    assert source_counts == {"marktechpost": 1, "simon willison": 1, "nature": 1}
    assert area_counts["mind_cognition"] == 1


def test_window_counts_empty_history_returns_empty_counts():
    source_counts, area_counts = pipeline._window_counts([], window_items=6)
    assert source_counts == {}
    assert area_counts == {}


def test_major_ai_product_launch_survives_the_bounded_global_ranking_window(monkeypatch):
    # Reproduce the failure mode: the product signal would fall outside the
    # 16-candidate window if freshness alone ordered the initial pool.
    monkeypatch.setattr(pipeline, "_exclude_published_candidates", lambda candidates: candidates)
    monkeypatch.setattr(
        pipeline,
        "freshness_score",
        lambda item, half_life_hours=36.0: float(item.get("_test_freshness", 0.0)),
    )
    monkeypatch.setattr(pipeline, "rerank_candidates", lambda candidates: candidates)
    monkeypatch.setattr(
        pipeline,
        "_diversify_normal_candidates",
        lambda normal, max_posts, *args, **kwargs: normal[:max_posts],
    )

    routine_items = [
        {
            "title": f"Routine AI deployment status update {index}",
            "summary": "A routine operational update about AI deployment.",
            "source": f"independent-source-{index}",
            "source_tier": 1,
            "content_type": "news",
            "_ai_link": True,
            "editorial_score_pre_signal": 82.0,
            "signal_score": 72.0,
            "_test_freshness": 0.88,
        }
        for index in range(18)
    ]
    product_launch = {
        "title": "Google DeepMind introduces Genie 4, an interactive world simulator",
        "summary": "The new world model generates interactive environments in real time.",
        "source": "Google DeepMind",
        "source_tier": 1,
        "content_type": "product_news",
        "_ai_link": True,
        "evidence_text": "Official product announcement",
        "editorial_score_pre_signal": 80.0,
        "signal_score": 70.0,
        "_test_freshness": 0.73,
    }

    ranked = pipeline._global_ranked_selection(
        routine_items + [product_launch],
        max_posts=8,
        max_per_source=2,
        max_per_type=8,
        policy={},
    )

    titles = [item["title"] for item in ranked]
    assert product_launch["title"] in titles
    assert ranked[0]["title"] == product_launch["title"]
    assert ranked[0]["major_ai_product_release"] is True
    # The discovery priority is used only before the bounded window is formed.


def test_bounded_discovery_priority_does_not_upgrade_generic_company_news():
    generic = {
        "title": "Google DeepMind announces a corporate partnership",
        "summary": "The organizations will work together on a business initiative.",
        "source": "Google DeepMind",
        "source_tier": 1,
        "content_type": "news",
        "_ai_link": True,
        "editorial_score_pre_signal": 80.0,
        "signal_score": 70.0,
    }
    pipeline._prepare_rank_features([generic])
    assert generic["major_ai_product_release"] is False
    assert generic["strategic_ai_leader_statement"] is False
    assert pipeline._bounded_discovery_priority_boost(generic) == 0.0



def test_product_release_priority_does_not_inflate_canonical_editorial_score():
    product_launch = {
        "title": "Google DeepMind introduces Genie 4, an interactive world simulator",
        "summary": "The new world model generates interactive environments in real time.",
        "source": "Google DeepMind",
        "source_tier": 1,
        "content_type": "product_news",
        "_ai_link": True,
        "evidence_text": "Official product announcement",
        "editorial_score_pre_signal": 80.0,
        "signal_score": 70.0,
    }
    expected_score = pipeline.canonical_rank_score(product_launch)
    pipeline._prepare_rank_features([product_launch])
    assert product_launch["major_ai_product_release"] is True
    assert product_launch["final_editorial_score"] == expected_score
    assert pipeline._bounded_discovery_priority_boost(product_launch) == 0.18
