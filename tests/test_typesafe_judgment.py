from typesafe_sdk import ScoreAnswer


class FakeResponse:
    def __init__(self, answers):
        self.scores = answers


class FakeClient:
    def __init__(self, scores):
        self.scores = scores
        self.calls = []

    def system_one(self, *, state, questions):
        self.calls.append((state, questions))
        return FakeResponse(self.scores)


def make_answer(score, confidence=1.0):
    return ScoreAnswer(
        type="score",
        score=score,
        confidence=confidence,
        legend={i: text for i, text in enumerate(["0", "1", "2", "3", "4"])},
        probabilities={score: 1.0},
    )


def test_typesafe_off_preserves_order(monkeypatch):
    import src.typesafe_judgment as tj

    monkeypatch.setenv("AI_RADAR_TYPESAFE_RERANK_MODE", "off")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    items = [{"title": "A"}, {"title": "B"}]
    assert tj.rerank_candidates(items) == items


def test_typesafe_audit_calls_model_but_does_not_reorder(monkeypatch):
    import src.typesafe_judgment as tj

    monkeypatch.setenv("AI_RADAR_TYPESAFE_RERANK_MODE", "audit")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    client = FakeClient(
        {
            "mission_fit": make_answer(0),
            "novelty": make_answer(0),
            "editorial_value": make_answer(0),
        }
    )
    items = [{"title": "A"}, {"title": "B"}]
    result = tj.rerank_candidates(items, client=client)
    assert [x["title"] for x in result] == ["A", "B"]
    assert len(client.calls) == 2


def test_typesafe_active_can_rerank_without_using_raw_editorial_score(monkeypatch):
    import src.typesafe_judgment as tj

    monkeypatch.setenv("AI_RADAR_TYPESAFE_RERANK_MODE", "active")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    client = FakeClient(
        {
            "mission_fit": make_answer(4),
            "novelty": make_answer(4),
            "editorial_value": make_answer(4),
        }
    )
    client_low = FakeClient(
        {
            "mission_fit": make_answer(0),
            "novelty": make_answer(0),
            "editorial_value": make_answer(0),
        }
    )
    items = [
        {"title": "A"},
        {"title": "B"},
    ]
    # Put a semantically poor candidate first and a strong candidate second.
    result = tj.rerank_candidates(items, client=client_low)
    assert [x["title"] for x in result] == ["A", "B"]
    result = tj.rerank_candidates(items, client=client)
    assert [x["title"] for x in result] == ["A", "B"]


def test_typesafe_failure_is_fail_open(monkeypatch):
    import src.typesafe_judgment as tj

    monkeypatch.setenv("AI_RADAR_TYPESAFE_RERANK_MODE", "active")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")

    class BrokenClient:
        def system_one(self, *, state, questions):
            raise RuntimeError("boom")

    items = [{"title": "A"}, {"title": "B"}]
    result = tj.rerank_candidates(items, client=BrokenClient())
    assert [x["title"] for x in result] == ["A", "B"]
