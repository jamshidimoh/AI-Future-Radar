from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "msa_v1_telegram_channels.json"
OUT = ROOT / "data" / "msa_v1_telegram_recent.jsonl"

POST_RE = re.compile(r'<div class="tgme_widget_message[^>]*data-post="([^"]+)"[^>]*>(.*?)</div>\\s*</div>', re.S)
TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', re.S)
DATE_RE = re.compile(r'<time[^>]+datetime="([^"]+)"')


def clean_html(value: str) -> str:
    value = re.sub(r'<br\\s*/?>', '\\n', value, flags=re.I)
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\\s+', ' ', unescape(value)).strip()


def fetch_channel(channel: str, cutoff: datetime) -> list[dict]:
    url = f"https://t.me/s/{channel}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 MSA-V1 benchmark"})
    with urlopen(req, timeout=20) as response:
        html = response.read().decode("utf-8", "replace")
    rows = []
    for post_id, body in POST_RE.findall(html):
        date_match = DATE_RE.search(body)
        if not date_match:
            continue
        try:
            published = datetime.fromisoformat(date_match.group(1).replace("Z", "+00:00"))
        except ValueError:
            continue
        if published < cutoff:
            continue
        text_match = TEXT_RE.search(body)
        text = clean_html(text_match.group(1)) if text_match else ""
        if not text:
            continue
        rows.append({
            "source_type": "telegram",
            "channel": channel,
            "post_id": post_id,
            "published_at": published.isoformat(),
            "url": f"https://t.me/{post_id}",
            "text": text,
        })
    return rows


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(config.get("window_days", 30)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    failures = []
    for channel in config["channels"]:
        try:
            rows = fetch_channel(channel, cutoff)
            all_rows.extend(rows)
            print(f"TELEGRAM_CHANNEL channel={channel} records={len(rows)} status=OK")
        except Exception as exc:
            failures.append(channel)
            print(f"TELEGRAM_CHANNEL channel={channel} records=0 status=ERROR error={type(exc).__name__}")
    all_rows.sort(key=lambda r: r["published_at"], reverse=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for row in all_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\\n")
    print(f"TELEGRAM_CORPUS records={len(all_rows)} channels={len(config['channels'])} failures={len(failures)}")
    print(f"TELEGRAM_CORPUS_OUTPUT={OUT.relative_to(ROOT)}")
    if failures:
        print("TELEGRAM_CORPUS_PARTIAL=true")
    return 0 if all_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
