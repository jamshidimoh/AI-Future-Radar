from src.education_production_fallback import publish_required_education


class Outcome:
    message_id = 42
    chat_id = "-100"

    def as_dict(self):
        return {"message_id": 42, "chat_id": "-100"}


def test_required_education_confirms_message_and_commits(tmp_path):
    calls = []
    item = {"education_id": 19, "term_a_definition": "الف", "title": "درس"}
    feedback = {"messages": {}}
    cadence = {"last_education_run": 0}

    ok = publish_required_education(
        run_number=7,
        feedback_path=tmp_path / "feedback.json",
        cadence=cadence,
        rewrite_fn=lambda x: x,
        fetch_builder=lambda: item,
        commit_lesson=lambda lesson: calls.append(("commit", lesson)),
        format_post=lambda x: "EDU",
        send=lambda *args, **kwargs: Outcome(),
        load_feedback=lambda path: feedback,
        register_post=lambda store, meta, story: calls.append(("ledger", meta["message_id"])),
        save_feedback=lambda store, path: calls.append(("save", True)),
    )

    assert ok is True
    assert cadence["last_education_run"] == 7
    assert ("ledger", 42) in calls
    assert ("commit", 19) in calls


def test_required_education_rejects_missing_message_id(tmp_path):
    class Failed:
        message_id = None

    ok = publish_required_education(
        run_number=7,
        feedback_path=tmp_path / "feedback.json",
        cadence={"last_education_run": 0},
        rewrite_fn=lambda x: x,
        fetch_builder=lambda: {"education_id": 19},
        commit_lesson=lambda lesson: None,
        format_post=lambda x: "EDU",
        send=lambda *args, **kwargs: Failed(),
        load_feedback=lambda path: {"messages": {}},
        register_post=lambda *args: None,
        save_feedback=lambda *args: None,
    )

    assert ok is False
