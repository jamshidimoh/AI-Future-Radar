"""Resilient YouTube discovery for AI Future Radar.

Order of retrieval:
1) YouTube Data API v3 when YOUTUBE_API_KEY is configured.
2) Channel RSS when available.
3) Public channel page using structured ytInitialData extraction.
4) Regex parser as a final HTML fallback.

A failure in one transport must never turn all monitored YouTube sources into
an unexplained zero-result run.
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone

import feedparser
import requests

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    TRANSCRIPT_AVAILABLE = True
except ImportError:
    TRANSCRIPT_AVAILABLE = False

_handle_to_id_cache: dict[str, str | None] = {}
_GENERIC_LOW_SIGNAL_KEYWORDS = {
    "unboxing", "unboxing video", "product review", "product showcase", "giveaway", "merch", "sponsor",
}
_KNOWN_CHANNEL_IDS = {
    "@80000hours": "UCafjal1QYJ3rb0Y9xZk1Ezg",
    "80000hours": "UCafjal1QYJ3rb0Y9xZk1Ezg",
    "@eightythousandhours": "UCafjal1QYJ3rb0Y9xZk1Ezg",
    "eightythousandhours": "UCafjal1QYJ3rb0Y9xZk1Ezg",
    "@instituteofartandideas": "UCTsiZiMomJo6FOyiBaFeaIw",
    "instituteofartandideas": "UCTsiZiMomJo6FOyiBaFeaIw",
}


def _normalize_handle(handle: str) -> str:
    value = str(handle or "").strip()
    return value if value.startswith("@") else f"@{value}"


def _extract_channel_id(text: str) -> str | None:
    for pattern in (
        r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
        r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
        r'/channel/(UC[a-zA-Z0-9_-]{22})',
        r'"browseId":"(UC[a-zA-Z0-9_-]{22})"',
    ):
        match = re.search(pattern, text or "")
        if match:
            return match.group(1)
    return None


def _resolve_handle_to_channel_id(handle: str) -> str | None:
    handle_clean = _normalize_handle(handle)
    cache_key = handle_clean.lower()
    if cache_key in _handle_to_id_cache:
        return _handle_to_id_cache[cache_key]
    known = _KNOWN_CHANNEL_IDS.get(cache_key)
    if known:
        _handle_to_id_cache[cache_key] = known
        return known

    urls = [
        f"https://www.youtube.com/{handle_clean}",
        f"https://www.youtube.com/{handle_clean}/about",
        f"https://www.youtube.com/{handle_clean}/videos",
        f"https://m.youtube.com/{handle_clean}",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    channel_id = None
    session = requests.Session()
    for url in urls:
        try:
            response = session.get(url, timeout=12, headers=headers, allow_redirects=True)
            if response.status_code >= 400:
                continue
            channel_id = _extract_channel_id(response.text)
            if channel_id:
                break
        except requests.RequestException:
            continue
    _handle_to_id_cache[cache_key] = channel_id
    return channel_id


def _parse_relative_age(label: str) -> str:
    raw = str(label or "").strip().lower()
    match = re.match(r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks)\s+ago", raw)
    if not match:
        return ""
    value = int(match.group(1))
    seconds = {
        "minute": 60, "minutes": 60,
        "hour": 3600, "hours": 3600,
        "day": 86400, "days": 86400,
        "week": 604800, "weeks": 604800,
    }[match.group(2)]
    return datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - value * seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _youtube_api_key() -> str:
    import os
    return str(os.environ.get("YOUTUBE_API_KEY") or "").strip()


def _fetch_via_data_api(channel_id: str, channel_name: str, cutoff: float) -> list[dict]:
    """Use official YouTube Data API when a key is configured.

    channels.list + playlistItems.list uses the channel's uploads playlist and
    avoids the 100-quota search endpoint.
    """
    key = _youtube_api_key()
    if not key:
        return []
    base = "https://www.googleapis.com/youtube/v3"
    try:
        channel_resp = requests.get(
            f"{base}/channels",
            params={"part": "contentDetails,snippet", "id": channel_id, "key": key},
            timeout=15,
        )
        channel_resp.raise_for_status()
        channel_items = channel_resp.json().get("items") or []
        if not channel_items:
            raise RuntimeError("channel not found by Data API")
        uploads_id = (((channel_items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads"))
        if not uploads_id:
            raise RuntimeError("uploads playlist unavailable")

        items_resp = requests.get(
            f"{base}/playlistItems",
            params={"part": "snippet,contentDetails", "playlistId": uploads_id, "maxResults": 50, "key": key},
            timeout=15,
        )
        items_resp.raise_for_status()
        items = items_resp.json().get("items") or []
        results = []
        for item in items:
            snippet = item.get("snippet") or {}
            video_id = str((item.get("contentDetails") or {}).get("videoId") or "").strip()
            title = str(snippet.get("title") or "").strip()
            published = str(snippet.get("publishedAt") or "").strip()
            if not video_id or not title:
                continue
            try:
                published_ts = datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp() if published else 0
            except ValueError:
                published_ts = 0
            if published_ts and published_ts < cutoff:
                continue
            results.append({
                "video_id": video_id,
                "title": html.unescape(title),
                "link": f"https://www.youtube.com/watch?v={video_id}",
                "summary": html.unescape(str(snippet.get("description") or "")),
                "published": datetime.fromtimestamp(published_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if published_ts else "",
            })
        if results:
            print(f"[YouTube Data API] channel={channel_name} items={len(results)}", flush=True)
        return results
    except requests.RequestException as exc:
        print(f"[WARN] YouTube Data API failed for {channel_name}: {exc}", flush=True)
    except (ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"[WARN] YouTube Data API parse failed for {channel_name}: {exc}", flush=True)
    return []


def _fetch_channel_feed(channel_id: str, channel_name: str):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    last_error = None
    for attempt, headers in enumerate((
        {"User-Agent": "AI-Future-Tech-Radar/1.0", "Accept-Language": "en-US,en;q=0.9"},
        {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
    ), 1):
        try:
            response = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
                raise RuntimeError("invalid RSS response")
            return feed
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.75)
    raise RuntimeError(f"YouTube RSS unavailable for {channel_name}: {last_error}")


def _walk_video_renderers(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        renderer = node.get("videoRenderer")
        if isinstance(renderer, dict):
            video_id = str(renderer.get("videoId") or "").strip()
            title = ""
            title_obj = renderer.get("title") or {}
            runs = title_obj.get("runs") or []
            if runs and isinstance(runs[0], dict):
                title = str(runs[0].get("text") or "").strip()
            if not title:
                title = str((title_obj.get("simpleText") or "")).strip()
            pub = str(((renderer.get("publishedTimeText") or {}).get("simpleText") or "")).strip()
            description_parts = []
            for detail in renderer.get("detailedMetadataSnippets") or []:
                snippet = detail.get("snippet") or {}
                runs = snippet.get("runs") or []
                if runs:
                    description_parts.extend(str(run.get("text") or "") for run in runs if isinstance(run, dict))
                elif snippet.get("simpleText"):
                    description_parts.append(str(snippet.get("simpleText")))
            if not description_parts:
                snippet = renderer.get("descriptionSnippet") or {}
                runs = snippet.get("runs") or []
                description_parts.extend(str(run.get("text") or "") for run in runs if isinstance(run, dict))
            description = html.unescape(" ".join(part for part in description_parts if part).strip())
            if video_id and title:
                out.append({
                    "video_id": video_id,
                    "title": html.unescape(title),
                    "published_label": html.unescape(pub),
                    "summary": description,
                })
        for value in node.values():
            _walk_video_renderers(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_video_renderers(value, out)


def _extract_yt_initial_data(text: str) -> dict | None:
    match = re.search(r"(?:var\s+ytInitialData\s*=|ytInitialData\s*=)\s*(\{.*?\})\s*;?\s*</script>", text, re.S)
    if not match:
        match = re.search(r"<script[^>]*id=\"ytInitialData\"[^>]*>(\{.*?\})</script>", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (ValueError, TypeError):
        return None


def _fetch_channel_page_items(channel_id: str, channel_name: str, cutoff: float) -> list[dict]:
    urls = [
        f"https://www.youtube.com/channel/{channel_id}/videos",
        f"https://www.youtube.com/channel/{channel_id}/featured",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for url in urls:
        try:
            response = requests.get(url, timeout=20, headers=headers, allow_redirects=True)
            if response.status_code >= 400:
                continue
            text = response.text[:8_000_000]
            data = _extract_yt_initial_data(text)
            extracted: list[dict] = []
            if data:
                _walk_video_renderers(data, extracted)
            if not extracted:
                pattern = re.compile(r'"videoId":"(?P<id>[A-Za-z0-9_-]{11})".{0,2000}?"title":\{"runs":\[\{"text":"(?P<title>(?:[^"\\]|\\.)+)', re.S)
                for match in pattern.finditer(text):
                    extracted.append({
                        "video_id": match.group("id"),
                        "title": html.unescape(match.group("title")).replace('\\"', '"'),
                        "published_label": "",
                    })
            results = []
            seen = set()
            for item in extracted:
                video_id = item.get("video_id")
                if not video_id or video_id in seen:
                    continue
                seen.add(video_id)
                published = _parse_relative_age(item.get("published_label"))
                if published:
                    try:
                        ts = datetime.strptime(published, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
                        if ts < cutoff:
                            continue
                    except ValueError:
                        pass
                results.append({
                    "video_id": video_id,
                    "title": item.get("title", ""),
                    "link": f"https://www.youtube.com/watch?v={video_id}",
                    "summary": str(item.get("summary") or ""),
                    "published": published,
                })
            if results:
                print(f"[YouTube Page Fallback] channel={channel_name} items={len(results)}", flush=True)
                return results
        except requests.RequestException as exc:
            print(f"[WARN] YouTube channel-page fallback failed for {channel_name}: {exc}", flush=True)
    return []


def _classify_video_content(title: str, description: str, channel: dict) -> str:
    explicit = str(channel.get("content_type") or "").strip()
    if explicit:
        return explicit
    text = f"{title} {description}".lower()
    if any(k in text for k in ("interview", "conversation", "talk to", "dialogue")):
        return "interview"
    if any(k in text for k in ("podcast", "episode", "conversation")):
        return "podcast"
    if any(k in text for k in ("paper", "research", "study", "lab", "model")):
        return "research"
    if any(k in text for k in ("lecture", "course", "class")):
        return "lecture"
    return "video"


def _is_low_signal_video(title: str, description: str, channel: dict) -> bool:
    text = f"{title} {description}".lower()
    excluded = {str(x).lower() for x in channel.get("exclude_title_keywords", [])}
    excluded.update(_GENERIC_LOW_SIGNAL_KEYWORDS)
    return any(keyword in text for keyword in excluded)


def _get_transcript_snippet(video_id: str, max_chars: int = 3000) -> str:
    if not TRANSCRIPT_AVAILABLE or not video_id:
        return ""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])
        return " ".join(seg["text"] for seg in transcript)[:max_chars]
    except Exception:
        return ""


def _normalize_video_result(channel: dict, item: dict) -> dict | None:
    title = str(item.get("title") or "").strip()
    if not title or _is_low_signal_video(title, str(item.get("summary") or ""), channel):
        return None
    video_id = str(item.get("video_id") or "").strip()
    raw_summary = str(item.get("summary") or "").strip()
    transcript = _get_transcript_snippet(video_id) if not raw_summary else ""
    evidence_text = transcript or raw_summary
    evidence_source = "transcript" if transcript else ("channel_page_description" if raw_summary else "none")
    return {
        "title": title,
        "link": item.get("link", ""),
        "summary": evidence_text[:2000],
        "evidence_text": evidence_text[:3000],
        "evidence_source": evidence_source,
        "source": f"YouTube - {channel['name']}",
        "category": channel.get("category", "ai"),
        "is_video": True,
        "published": item.get("published", ""),
        "source_tier": channel.get("tier", 2),
        "source_type": channel.get("type", "youtube"),
        "content_type": _classify_video_content(title, str(item.get("summary") or ""), channel),
        "official": bool(channel.get("official", True)),
    }


def fetch_youtube_items(youtube_channels, max_age_hours=72, ai_bridge_keywords=None):
    results = []
    cutoff = time.time() - (min(max_age_hours, 720) * 3600)
    api_configured = bool(_youtube_api_key())
    print(f"[YouTube Discovery] api_key={'configured' if api_configured else 'not_configured'} channels={len(youtube_channels)}", flush=True)

    for channel in youtube_channels:
        channel_id = channel.get("channel_id")
        if not channel_id and channel.get("handle"):
            channel_id = _resolve_handle_to_channel_id(channel["handle"])
        if not channel_id:
            print(f"[WARN] YouTube channel {channel.get('name', '<unnamed>')!r} has no resolvable channel_id", flush=True)
            continue

        entries = _fetch_via_data_api(channel_id, channel.get("name", channel_id), cutoff) if api_configured else []
        source_used = "data-api" if entries else ""

        if not entries:
            try:
                feed = _fetch_channel_feed(channel_id, channel.get("name", channel_id))
                for entry in list(getattr(feed, "entries", []) or []):
                    published = entry.get("published_parsed")
                    published_str = ""
                    if published:
                        ts = time.mktime(published)
                        if ts < cutoff:
                            continue
                        published_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    entries.append({
                        "video_id": entry.get("yt_videoid", ""),
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": published_str,
                    })
                if entries:
                    source_used = "rss"
            except Exception as exc:
                print(f"[WARN] YouTube RSS failed for {channel.get('name', channel_id)}: {exc}", flush=True)

        if not entries:
            entries = _fetch_channel_page_items(channel_id, channel.get("name", channel_id), cutoff)
            if entries:
                source_used = "channel-page"

        if entries:
            added = 0
            for item in entries:
                normalized = _normalize_video_result(channel, item)
                if normalized:
                    results.append(normalized)
                    added += 1
            print(f"[YouTube Source] channel={channel.get('name', channel_id)} source={source_used} accepted={added}", flush=True)
        else:
            print(f"[WARN] YouTube source unavailable after Data API/RSS/page fallback: {channel.get('name', channel_id)}", flush=True)

    return results
