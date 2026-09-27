from src.topic_repetition_guard import filter_history_topic_repetition


def _sig(title, summary, anchors):
    return {
        "title_text": title,
        "title": title.split(),
        "context": f"{title} {summary}".split(),
        "anchors": anchors,
        "events": [],
        "personnel": [],
        "numbers": [],
        "leader": "",
    }


def test_history_topic_repetition_blocks_cross_source_rewrite():
    history = [_sig("OpenAI launches a new reasoning model", "OpenAI model reasoning launch", ["openai", "reasoning"])]
    candidates = [
        {"title": "New OpenAI reasoning model launches", "summary": "OpenAI launches a reasoning model with new capabilities."},
        {"title": "Quantum sensor breakthrough for materials", "summary": "A quantum sensing system improves material analysis."},
    ]
    kept, blocked = filter_history_topic_repetition(
        candidates,
        history,
        threshold=0.55,
        soft_threshold=0.50,
        min_anchor_overlap=1,
    )
    assert blocked == 1
    assert kept[0]["title"].startswith("Quantum")


def test_history_topic_guard_does_not_block_generic_ai_only_overlap():
    history = [_sig("New AI system announced", "AI system development", ["ai"])]
    candidates = [{"title": "AI research advances", "summary": "A different research result in AI."}]
    kept, blocked = filter_history_topic_repetition(
        candidates,
        history,
        threshold=0.55,
        soft_threshold=0.50,
        min_anchor_overlap=1,
    )
    assert blocked == 0
    assert kept == candidates
