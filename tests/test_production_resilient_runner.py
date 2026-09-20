import importlib


def test_resilient_runner_bootstraps_src_import_path():
    module = importlib.import_module("production_resilient_runner")
    assert module.educational_content.__name__ == "src.educational_content"
    assert hasattr(module.educational_content, "build_educational_item")


def test_watchdog_minutes_default_and_env(monkeypatch):
    module = importlib.import_module("production_resilient_runner")

    monkeypatch.delenv("RADAR_WATCHDOG_MINUTES", raising=False)
    assert module._watchdog_minutes() == module.DEFAULT_WATCHDOG_MINUTES

    monkeypatch.setenv("RADAR_WATCHDOG_MINUTES", "7")
    assert module._watchdog_minutes() == 7


def test_watchdog_minutes_invalid_and_non_positive_values_fall_back(monkeypatch):
    module = importlib.import_module("production_resilient_runner")

    monkeypatch.setenv("RADAR_WATCHDOG_MINUTES", "not-a-number")
    assert module._watchdog_minutes() == module.DEFAULT_WATCHDOG_MINUTES

    monkeypatch.setenv("RADAR_WATCHDOG_MINUTES", "0")
    assert module._watchdog_minutes() == 1

    monkeypatch.setenv("RADAR_WATCHDOG_MINUTES", "-5")
    assert module._watchdog_minutes() == 1



def test_main_applies_production_router_policy_before_entrypoint(monkeypatch):
    module = importlib.import_module("production_resilient_runner")
    calls = []

    monkeypatch.setenv("RADAR_PRODUCTION_MODE", "1")
    monkeypatch.setattr(module, "configure_logging", lambda: None)
    monkeypatch.setattr(module, "apply_production_router_policy", lambda: calls.append("policy"))
    monkeypatch.setattr(module, "load_editorial_contract", lambda: {"candidate_window": 6, "max_posts": 3})
    monkeypatch.setattr(module, "_watchdog_minutes", lambda: 1)
    monkeypatch.setattr(module.faulthandler, "dump_traceback_later", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.faulthandler, "cancel_dump_traceback_later", lambda: None)
    monkeypatch.setattr(module.production_entrypoint, "main", lambda: calls.append("entrypoint") or 0)

    assert module.main() == 0
    assert calls == ["policy", "entrypoint"]
