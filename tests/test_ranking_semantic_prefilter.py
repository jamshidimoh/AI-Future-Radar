from period_ranked_pipeline import _semantic_comparison_possible


def test_semantic_prefilter_keeps_shared_anchor_candidates_for_full_guard():
    candidate = {
        "title": "OpenAI launches a new reasoning model",
        "summary": "OpenAI released a new reasoning model for advanced AI workloads.",
    }
    record = {
        "title": "OpenAI introduces its latest reasoning model",
        "summary": "The company introduced the latest reasoning model for advanced AI workloads.",
    }
    assert _semantic_comparison_possible(candidate["title"], candidate["summary"], record)


def test_semantic_prefilter_keeps_close_title_rewrites_without_shared_anchors():
    candidate = {
        "title": "New quantum benchmark released for researchers",
        "summary": "A new benchmark was released for researchers.",
    }
    record = {
        "title": "New quantum benchmark released for research teams",
        "summary": "A benchmark was released for research teams.",
    }
    assert _semantic_comparison_possible(candidate["title"], candidate["summary"], record)


def test_semantic_prefilter_skips_obviously_unrelated_stories():
    candidate = {
        "title": "Copper infrastructure investment expands in Europe",
        "summary": "A major infrastructure project received new investment.",
    }
    record = {
        "title": "Women's health study reports new findings",
        "summary": "Researchers reported new findings from a health study.",
    }
    assert not _semantic_comparison_possible(candidate["title"], candidate["summary"], record)
