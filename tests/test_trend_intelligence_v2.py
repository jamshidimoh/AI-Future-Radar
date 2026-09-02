from src.trend_intelligence_v2 import run_current_window


def test_current_window_adapter_persists_g2_identity(tmp_path):
    path = tmp_path / "trend_registry.json"
    items = [
        {"id": "s1", "title": "AI agents improve research workflows", "signal_score": 70, "source": "one"},
        {"id": "s2", "title": "AI agents improve scientific research workflows", "signal_score": 72, "source": "two"},
        {"id": "s3", "title": "Quantum hardware maintenance update", "signal_score": 60, "source": "three"},
    ]
    first = run_current_window(items, registry_path=path, run_id="r1", run_index=1)
    assert len(first["clusters"]) == 1
    first_id = first["registry"]["clusters"].keys()
    first_id = next(iter(first_id))

    second = run_current_window(items, registry_path=path, run_id="r2", run_index=2)
    assert next(iter(second["registry"]["clusters"])) == first_id
    assert second["registry"]["last_run_index"] == 2
