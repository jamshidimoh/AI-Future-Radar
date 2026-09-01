from src.fetch_google_news import _expand_leader_signal_queries, _has_leader_signal_evidence, classify_leader_signal


def test_leader_signal_expansion_adds_one_companion_per_person():
    queries = [
        {"query": "Elon Musk AI xAI future interview", "watch_person": "Elon Musk", "category": "ai", "tier": 1, "content_type": "interview"},
        {"query": "Elon Musk xAI product launch", "watch_person": "Elon Musk", "category": "ai", "tier": 1, "content_type": "product_news"},
        {"query": "Sam Altman AI AGI interview", "watch_person": "Sam Altman", "category": "ai", "tier": 1, "content_type": "interview"},
    ]
    expanded = _expand_leader_signal_queries(queries)
    companions = [q for q in expanded if q.get("content_type") == "leader_signal"]
    assert len(expanded) == len(queries) + 2
    assert {q["watch_person"] for q in companions} == {"Elon Musk", "Sam Altman"}
    assert all(q.get("leader_discovery") is True for q in companions)
    assert all(q.get("curated_discovery") is True for q in companions)
    assert all("Europe" in q["query"] for q in companions)
    assert all("policy" in q["query"] for q in companions)
    assert all("tweet" in q["query"] for q in companions)


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


def test_strategic_musk_eu_signal_is_kept():
    result = classify_leader_signal(
        "Musk defends AI data centers, slams EU rules at G20",
        "Elon Musk criticized European regulation affecting AI data centers and technology companies.",
    )
    assert result == {"accepted": True, "interview": False, "activity": True, "context": True}


def test_interview_signal_is_kept_with_technology_context():
    result = classify_leader_signal(
        "Fei-Fei Li interview on the future of AI and robotics",
        "A substantive podcast conversation about AI research, robotics and education.",
    )
    assert result["accepted"] is True
    assert result["interview"] is True
    assert result["context"] is True


def test_non_substantive_ceo_story_is_rejected():
    result = classify_leader_signal(
        "List of the Famous CEOs and Billionaires Who Have Attended Burning Man",
        "A list of executives and billionaires who attended the event.",
    )
    assert result["accepted"] is False


def test_strategic_leader_outlook_signal_is_kept():
    result = classify_leader_signal(
        "Sam Altman says AI adoption is slower than expected",
        "The OpenAI CEO says the economy is taking longer to adapt to artificial intelligence.",
    )
    assert result["accepted"] is True
    assert result["activity"] is True
    assert result["context"] is True
