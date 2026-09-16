from pathlib import Path

from src.rejection_telemetry import RejectionEvent, build_event, emit


def test_build_event_normalizes_common_fields():
    event = build_event(
        run_id="123",
        run_number=9,
        trace_id="trace",
        item_id="item",
        stage="publication_contract",
        decision="reject",
        reason_code="normal_score_floor",
        item={
            "mission_area": "mind_cognition",
            "content_type": "research",
            "source": "Nature",
            "source_tier": "1",
            "global_rank": "5",
            "normal_rank": "2",
            "signal_score": "54.99",
        },
        details={"floor": 55.0},
        attempt=1,
        replacement_eligible=True,
    )
    assert isinstance(event, RejectionEvent)
    data = event.to_dict()
    assert data["schema_version"] == "rejection-event.v1"
    assert data["source_tier"] == 1
    assert data["global_rank"] == 5
    assert data["signal_score"] == 54.99
    assert data["details"]["floor"] == 55.0


def test_emit_appends_jsonl(tmp_path: Path):
    path = tmp_path / "trace" / "rejection_trace.jsonl"
    event = build_event(
        run_id="1",
        trace_id="t",
        item_id="i",
        stage="summarization",
        decision="recover",
        reason_code="provider_quota_exceeded",
    )
    emit(event, path)
    line = path.read_text(encoding="utf-8").strip()
    assert '"reason_code": "provider_quota_exceeded"' in line


def test_emit_is_fail_safe(tmp_path: Path):
    event = build_event(
        run_id="1",
        trace_id="t",
        item_id="i",
        stage="x",
        decision="reject",
        reason_code="x",
    )
    emit(event, tmp_path / "file")
    assert not (tmp_path / "file").is_dir()
