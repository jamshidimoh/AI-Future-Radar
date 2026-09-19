from typesafe_sdk import ScoreAnswer


class FakeResponse:
    def __init__(self, answers):
        self.scores = answers


class FakeClient:
    def __init__(self, answers_by_title):
        self.answers_by_title = answers_by_title
        self.calls = []

    def system_one(self, *, state, questions):
        title = state["candidate"]["title"]
        self.calls.append((state, questions))
        return FakeResponse(self.answers_by_title[title])


def make_answer(score, confidence=1.0):
    return ScoreAnswer(
        type="score",
        score=score,
        confidence=confidence,
        legend={i: text for i, text in enumerate(["0", "1", "2", "3", "4"])},
        probabilities={score: 1.0},
    )


def answer_set(score, confidence=1.0):
    return {
        "mission_fit": make_answer(score, confidence),
        "novelty": make_answer(score, confidence),
        "editorial_value": make_answer(score, confidence),
    }


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
    client = FakeClient({"A": answer_set(0), "B": answer_set(4)})
    items = [{"title": "A"}, {"title": "B"}]
    result = tj.rerank_candidates(items, client=client)
    assert [x["title"] for x in result] == ["A", "B"]
    assert len(client.calls) == 2
    assert result[0]["typesafe_judgment_score"] < result[1]["typesafe_judgment_score"]


def test_typesafe_active_reranks_the_bounded_window(monkeypatch):
    import src.typesafe_judgment as tj

    monkeypatch.setenv("AI_RADAR_TYPESAFE_RERANK_MODE", "active")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    client = FakeClient({"A": answer_set(0), "B": answer_set(4)})
    items = [{"title": "A"}, {"title": "B"}]
    result = tj.rerank_candidates(items, client=client)
    assert [x["title"] for x in result] == ["B", "A"]
    assert all(x["typesafe_rerank_applied"] for x in result)


def test_typesafe_low_confidence_attenuates_semantic_signal(monkeypatch):
    import src.typesafe_judgment as tj

    monkeypatch.setenv("AI_RADAR_TYPESAFE_RERANK_MODE", "active")
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    client = FakeClient({"A": answer_set(4, 0.0), "B": answer_set(0, 1.0)})
    items = [{"title": "A"}, {"title": "B"}]
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
