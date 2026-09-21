from src.fetch_google_news import _expand_leader_signal_queries, _has_leader_signal_evidence, classify_leader_signal


def test_leader_signal_expansion_is_person_agnostic():
    queries = [
        {"query": "Elon Musk AI xAI future interview", "watch_person": "Elon Musk", "category": "ai", "tier": 1, "content_type": "interview"},
        {"query": "Yuval Noah Harari AI future interview", "watch_person": "Yuval Noah Harari", "category": "future", "tier": 1, "content_type": "interview"},
        {"query": "David Chalmers AI consciousness interview", "watch_person": "David Chalmers", "category": "mind", "tier": 1, "content_type": "interview"},
    ]
    expanded = _expand_leader_signal_queries(queries)
    companions = [q for q in expanded if q.get("content_type") == "leader_signal"]
    assert len(expanded) == len(queries) + 3
    assert {q["watch_person"] for q in companions} == {"Elon Musk", "Yuval Noah Harari", "David Chalmers"}
    assert all(q.get("leader_discovery") is True for q in companions)
    assert all(q.get("curated_discovery") is True for q in companions)
    assert all("interview" in q["query"] for q in companions)
    assert all("podcast" in q["query"] for q in companions)
    assert all("analysis" in q["query"] for q in companions)
    assert all("forecast" in q["query"] for q in companions)


def test_base_queries_without_leaders_are_unchanged():
    queries = [{"query": "AI drug discovery breakthrough", "category": "genetics", "tier": 1, "content_type": "research"}]
    assert _expand_leader_signal_queries(queries) == queries


def test_weak_leader_mention_is_not_signal_evidence():
    assert not _has_leader_signal_evidence(
        "List of the Famous CEOs and Billionaires Who Have Attended Burning Man",
        "A list of executives and billionaires who attended the event.",
    )


def test_substantive_leader_statement_is_signal_evidence():
    assert _has_leader_signal_evidence(
        "Elon Musk criticizes EU technology regulation",
        "Musk said the policy could hinder technology development.",
    )


def test_strategic_leader_activity_signal_is_kept_across_people():
    cases = [
        ("Musk defends AI data centers, slams EU rules at G20", "Elon Musk criticized European regulation affecting AI data centers and technology companies."),
        ("Sam Altman says AI adoption is slower than expected", "The OpenAI CEO says the economy is taking longer to adapt to artificial intelligence."),
        ("Jensen Huang outlines the future of AI infrastructure", "NVIDIA's CEO discusses computing, chips and the long-term AI infrastructure outlook."),
    ]
    for title, summary in cases:
        result = classify_leader_signal(title, summary)
        assert result["accepted"] is True
        assert result["context"] is True


def test_substantive_interview_signal_is_kept_across_content_families():
    cases = [
        ("Fei-Fei Li interview on the future of AI and robotics", "A substantive podcast conversation about AI research, robotics and education."),
        ("Yuval Noah Harari discusses AI and social rules", "A long-form conversation about how artificial intelligence may reshape society, intimacy and governance."),
        ("David Chalmers on AI consciousness", "A discussion of artificial intelligence consciousness and what it could mean for science."),
        ("Ray Kurzweil on the technological singularity", "A discussion of long-term AI predictions, the singularity and future technology."),
    ]
    for title, summary in cases:
        result = classify_leader_signal(title, summary)
        assert result["accepted"] is True
        assert result["context"] is True
        assert result["interview"] or result["analytical"]


def test_non_substantive_ceo_story_is_rejected():
    result = classify_leader_signal(
        "List of the Famous CEOs and Billionaires Who Have Attended Burning Man",
        "A list of executives and billionaires who attended the event.",
    )
    assert result["accepted"] is False


def test_strategic_analysis_without_person_name_is_kept():
    result = classify_leader_signal(
        "Why the AI economy is like a bad dating app",
        "An analysis of the AI economy, enterprise adoption and the implications for work and business.",
    )
    assert result["accepted"] is True
    assert result["analytical"] is True
    assert result["context"] is True


def test_named_watch_query_recovers_sparse_google_news_snippet():
    result = classify_leader_signal(
        "The full conversation is now available",
        "A long-form discussion covers frontier AI systems and their future implications.",
        "Sam Altman",
        query_context='"Sam Altman" (interview OR podcast OR future OR artificial intelligence)',
        content_type="interview",
    )
    assert result["accepted"] is True
    assert result["person_signal"] is False
    assert result["query_person_signal"] is True


def test_named_watch_query_does_not_rescue_non_ai_query():
    result = classify_leader_signal(
        "The full conversation is now available",
        "A long-form discussion covers unrelated business topics.",
        "Sam Altman",
        query_context='"Sam Altman" (interview OR podcast)',
        content_type="interview",
    )
    assert result["accepted"] is False
