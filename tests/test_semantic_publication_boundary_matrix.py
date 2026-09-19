import src.publication_guard as publication_guard


def _candidate(title, summary):
    return (
        f"<b>📡 {title}</b>\n"
        f"<blockquote>📌 <b>خلاصه</b>\n{summary}</blockquote>"
    )


def test_translation_of_same_story_from_different_sources_is_blocked():
    published = {
        "title": "Coursera backs Andrew Ng's new AI education firm with a $100 million investment",
        "summary": "Coursera is investing $100 million in Andrew Ng's new AI education firm.",
        "link": "https://example.com/source-a",
    }
    candidate = _candidate(
        "سرمایه‌گذاری ۱۰۰ میلیون دلاری Coursera در شرکت آموزشی هوش مصنوعی جدید Andrew Ng",
        "Coursera ۱۰۰ میلیون دلار در شرکت آموزشی جدید Andrew Ng سرمایه‌گذاری می‌کند.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/source-b", records=[published]
    )
    assert not allowed
    assert reason.startswith("semantic_story_already_published")


def test_same_topic_but_distinct_research_event_remains_publishable():
    published = {
        "title": "Anil Seth discusses whether AI systems could appear conscious",
        "summary": "A discussion explores the social implications of apparently conscious AI systems.",
        "link": "https://example.com/social-consciousness",
    }
    candidate = _candidate(
        "Researchers introduce a new experiment for detecting signs of consciousness in language models",
        "A new study proposes an experimental method for testing consciousness-like signals in language models.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/research-consciousness", records=[published]
    )
    assert allowed, reason


def test_same_company_but_distinct_research_subject_remains_publishable():
    published = {
        "title": "NVIDIA researchers develop a more efficient AI inference accelerator",
        "summary": "NVIDIA presents research on reducing inference energy for large AI models.",
        "link": "https://example.com/nvidia-inference",
    }
    candidate = _candidate(
        "NVIDIA researchers publish a new method for robot perception",
        "The new research studies perception methods for autonomous robots.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/nvidia-robot-perception", records=[published]
    )
    assert allowed, reason


def test_same_leader_but_new_product_event_remains_publishable():
    published = {
        "title": "Sam Altman warns about the social effects of increasingly capable AI",
        "summary": "Sam Altman discusses social risks associated with increasingly capable AI systems.",
        "link": "https://example.com/altman-social",
    }
    candidate = _candidate(
        "Sam Altman announces a new AI agents product direction",
        "Sam Altman discusses a separate product direction focused on autonomous AI agents.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/altman-agents", records=[published]
    )
    assert allowed, reason


def test_same_story_with_different_urls_and_strong_title_overlap_is_blocked():
    published = {
        "title": "OpenAI launches a new reasoning model for enterprise work",
        "summary": "OpenAI launches a reasoning model designed for enterprise tasks.",
        "link": "https://example.com/openai-a",
    }
    candidate = _candidate(
        "OpenAI announces a new reasoning model for enterprise work",
        "The company announces the same reasoning model for enterprise tasks.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/openai-b", records=[published]
    )
    assert not allowed
    assert reason.startswith("semantic_story_already_published")


def test_shared_generic_ai_concept_without_story_identity_remains_publishable():
    published = {
        "title": "AI consciousness debates raise questions about social policy",
        "summary": "A commentary examines social and legal questions around apparently conscious AI.",
        "link": "https://example.com/commentary",
    }
    candidate = _candidate(
        "New benchmark evaluates reasoning reliability in large language models",
        "A new benchmark measures reliability and consistency in language-model reasoning.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/benchmark", records=[published]
    )
    assert allowed, reason

