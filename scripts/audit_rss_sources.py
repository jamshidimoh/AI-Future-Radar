"""Live audit for configured RSS sources.

This is intentionally a standalone audit rather than a production gate: external
feeds can transiently fail, but the report makes availability and parser health
visible before a source is promoted into the production registry.
"""
from __future__ import annotations

from pathlib import Path

import feedparser
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 12
USER_AGENT = "AI-Future-Radar/1.0 RSS audit"
SOURCE_CONFIGS = (
    ROOT / "config" / "sources.yaml",
    ROOT / "config" / "anthropic_rss_sources.yaml",
)


def _load_sources():
    sources = []
    seen = set()
    for config_path in SOURCE_CONFIGS:
        if not config_path.exists():
            continue
        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        for source in payload.get("rss_sources", []):
            if not isinstance(source, dict):
                continue
            url = str(source.get("url", "")).rstrip("/")
            if not url or url in seen:
                continue
            sources.append(source)
            seen.add(url)
    return sources


def main() -> int:
    sources = _load_sources()
    failures = 0
    print(f"RSS source audit: {len(sources)} configured feeds")
    for source in sources:
        name = source["name"]
        url = source["url"]
        try:
            response = requests.get(
                url,
                timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            entries = getattr(feed, "entries", [])
            bozo = bool(getattr(feed, "bozo", False))
            if not entries:
                failures += 1
                print(f"FAIL {name}: HTTP {response.status_code}, parsed=0, bozo={bozo}, url={response.url}")
                continue
            print(f"PASS {name}: HTTP {response.status_code}, parsed={len(entries)}, bozo={bozo}, url={response.url}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")

    print(f"RSS audit result: {'PASS' if failures == 0 else 'FAIL'}; failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
