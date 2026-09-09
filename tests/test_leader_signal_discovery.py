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
    assert result["accepted"] is True
    assert result["activity"] is True
    assert result["context"] is True


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


def test_harari_intimacy_future_signal_is_kept():
    result = classify_leader_signal(
        "Yuval Noah Harari: AI Will Mass-Produce Intimacy, and We Have Until 2028 to Set the Rules",
        "Harari discusses how artificial intelligence may reshape intimacy and social rules.",
        "Yuval Noah Harari",
    )
    assert result["accepted"] is True
    assert result["analytical"] is True
    assert result["context"] is True


def test_harari_intimacy_business_signal_is_kept():
    result = classify_leader_signal(
        "Yuval Noah Harari: AI Is Now in the Intimacy Business, and We Have Until 2028 to Set the Rules",
        "Harari examines AI, intimacy and the need for rules before 2028.",
        "Yuval Noah Harari",
    )
    assert result["accepted"] is True
    assert result["analytical"] is True
    assert result["context"] is True


def test_ai_consciousness_study_signal_is_kept():
    result = classify_leader_signal(
        "Study A.I. Consciousness? The Bots Would Like a Word With You. - The New York Times",
        "A study of artificial intelligence consciousness and what it could mean for science.",
        "David Chalmers",
    )
    assert result["accepted"] is True
    assert result["analytical"] is True
    assert result["context"] is True


def test_ai_economy_analysis_signal_is_kept():
    result = classify_leader_signal(
        "Why the AI economy is like a bad dating app — drowning in decks, pilot purgatory — and it's playing",
        "An analysis of the AI economy, enterprise adoption and the implications for work and business.",
        "Amy Webb",
    )
    assert result["accepted"] is True
    assert result["analytical"] is True
    assert result["context"] is True


def test_kurzweil_singularity_signal_is_kept():
    result = classify_leader_signal(
        "Ray Kurzweil: Living In The Singularity 2026 | by Tim Ventura | Predict | Aug, 2026",
        "A discussion of Ray Kurzweil's singularity outlook and long-term technology predictions.",
        "Ray Kurzweil",
    )
    assert result["accepted"] is True
    assert result["analytical"] is True
    assert result["context"] is True
