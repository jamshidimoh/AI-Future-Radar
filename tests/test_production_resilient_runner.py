import importlib


def test_resilient_runner_bootstraps_src_import_path():
    module = importlib.import_module("production_resilient_runner")
    assert module.educational_content.__name__ == "educational_content"
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
