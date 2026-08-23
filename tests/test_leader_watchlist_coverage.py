from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "leader_watchlist.yaml"


def _config():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _watch_people(config):
    people = set()
    for group in (config.get("people") or {}).values():
        people.update(str(name).strip() for name in (group.get("names") or []) if str(name).strip())
    return people


def test_every_watchlist_person_has_direct_google_news_discovery_query():
    config = _config()
    people = _watch_people(config)
    queried = {
        str(item.get("watch_person") or "").strip()
        for item in (config.get("google_news_queries") or [])
        if str(item.get("watch_person") or "").strip()
    }
    missing = sorted(people - queried)
    assert not missing, f"Watchlist people without Google News discovery queries: {missing}"


def test_every_watchlist_person_has_interview_or_expert_signal_query():
    config = _config()
    people = _watch_people(config)
    query_people = {
        str(item.get("watch_person") or "").strip()
        for item in (config.get("google_news_queries") or [])
        if str(item.get("watch_person") or "").strip()
        and str(item.get("content_type") or "").lower() in {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a"}
    }
    missing = sorted(people - query_people)
    assert not missing, f"Watchlist people without an interview/expert discovery query: {missing}"


def test_no_discovery_query_targets_unknown_watchlist_person():
    config = _config()
    people = _watch_people(config)
    unknown = sorted({
        str(item.get("watch_person") or "").strip()
        for item in (config.get("google_news_queries") or [])
        if str(item.get("watch_person") or "").strip() and str(item.get("watch_person")).strip() not in people
    })
    assert not unknown, f"Discovery queries target people not registered in Watchlist: {unknown}"
