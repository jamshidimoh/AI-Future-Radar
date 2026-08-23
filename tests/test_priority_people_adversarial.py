from src.priority_people import priority_people_features


def test_quote_only_news_is_not_tier0():
    item = {
        "title": "AI market activity accelerates",
        "summary": "Mark Zuckerberg said companies must adapt as the market changes.",
        "description": "A news report covers several transactions and quotes Zuckerberg.",
        "content_type": "news",
        "source": "News",
        "key_quote": "The market is changing rapidly and companies must adapt.",
    }
    people, is_tier0, bonus = priority_people_features(item)
    assert "mark zuckerberg" in people
    assert is_tier0 is False
    assert bonus == 0.0


def test_interview_with_substantive_content_is_tier0():
    item = {
        "title": "Mark Zuckerberg in conversation about the future of AI",
        "summary": "An extended interview explores Meta's AI strategy and the future of open models.",
        "description": "The conversation covers model development, agents, safety, and long-term strategy.",
        "content_type": "interview",
        "source": "Podcast",
    }
    people, is_tier0, bonus = priority_people_features(item)
    assert "mark zuckerberg" in people
    assert is_tier0 is True
    assert bonus == 50.0


def test_interview_label_alone_does_not_make_short_content_tier0():
    item = {
        "title": "Interview: Sam Altman",
        "summary": "Short item.",
        "description": "Brief metadata only.",
        "content_type": "interview",
        "source": "News",
    }
    people, is_tier0, bonus = priority_people_features(item)
    assert "sam altman" in people
    assert is_tier0 is False
    assert bonus == 0.0


def test_non_interview_title_with_person_name_stays_normal_news():
    item = {
        "title": "Mark Zuckerberg announces new AI investment",
        "summary": "The company announced a new investment and partnership.",
        "description": "The report mentions Zuckerberg but is ordinary news coverage.",
        "content_type": "news",
        "source": "News",
    }
    people, is_tier0, bonus = priority_people_features(item)
    assert "mark zuckerberg" in people
    assert is_tier0 is False
    assert bonus == 0.0


def test_persian_interview_remains_tier0():
    item = {
        "title": "مصاحبه با سم آلتمن درباره آینده هوش مصنوعی",
        "summary": "گفت‌وگوی مفصل درباره مدل‌های آینده، عامل‌ها و راهبرد بلندمدت هوش مصنوعی.",
        "description": "این مصاحبه درباره توسعه مدل، ایمنی و آینده سامانه‌های هوشمند است.",
        "content_type": "interview",
        "source": "Podcast",
    }
    people, is_tier0, bonus = priority_people_features(item)
    assert is_tier0 is True
    assert bonus == 50.0


def test_ambiguous_surname_does_not_match_ordinary_news():
    item = {
        "title": "The Russell report reviews AI regulation",
        "summary": "The report reviews policy developments and market trends.",
        "description": "No interview or direct discussion is present.",
        "content_type": "news",
        "source": "News",
    }
    people, is_tier0, bonus = priority_people_features(item)
    assert "stuart russell" not in people
    assert is_tier0 is False
    assert bonus == 0.0
