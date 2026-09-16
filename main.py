import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from src.dedup import filter_new_items, load_seen, load_source_history, mark_as_seen, save_seen
from src.editorial import enrich_items, filter_ai_relevance
from src.fetch_google_news import fetch_google_news_items
from src.fetch_rss import fetch_rss_items
from src.fetch_youtube import fetch_youtube_items
from src.interview_evidence import has_interview_evidence
from src.llm_router_light import QuotaExceeded
from src.logging_setup import configure_logging
from src.mission_selector import _source_tier
from src.publication_contract import unique_candidates
from src.rejection_telemetry import build_event, emit
from src.send_telegram import format_post, resolve_source_image, send_to_telegram_safe
from src.signal_engine import enrich_signal_items
from src.state_io import StateCorruptionError
from src.story_gate import gate_story_candidates
from src.summarize import summarize_item
from src.unified_editorial_selection import select_regular_portfolio

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
LEADER_CONFIG_PATH = ROOT / "config" / "leader_watchlist.yaml"
SELECTION_POLICY_PATH = ROOT / "config" / "selection_policy.yaml"
TELEGRAM_SAFE_TEXT_LIMIT = 3900
PROTECTED_SUMMARY_SCORE_FLOOR = 60.0
NORMAL_SCORE_FLOOR = 60.0
MAX_MIND_IDEAS_VOICES_PER_PERIOD = 2


def _is_mind_ideas_voices(item: dict) -> bool:
    return bool(
        item.get("mind_lane_selected")
        or item.get("protected_editorial_lane") == "mind_ideas_voices"
        or item.get("lane") == "mind_ideas_voices"
    )


def _publication_identity(item: dict) -> str:
    return str(item.get("canonical_url") or item.get("link") or item.get("url") or item.get("title") or id(item))


def _runtime_telemetry_event(item: dict, *, stage: str, decision: str, reason_code: str, details=None, attempt=None) -> None:
    try:
        identity = _publication_identity(item)
        trace_id = __import__("hashlib").sha1(identity.encode("utf-8", errors="ignore")).hexdigest()[:16]
        run_id = str(os.getenv("GITHUB_RUN_ID") or os.getenv("RADAR_RUN_ID") or "local")
        raw_run_number = os.getenv("GITHUB_RUN_NUMBER") or os.getenv("RADAR_RUN_NUMBER")
        try:
            run_number = int(raw_run_number) if raw_run_number is not None else None
        except (TypeError, ValueError):
            run_number = None
        path = Path(os.getenv("RADAR_REJECTION_TRACE_PATH", "artifacts/rejection_trace/rejection_trace.jsonl"))
        emit(
            build_event(
                run_id=run_id,
                run_number=run_number,
                trace_id=trace_id,
                item_id=identity,
                stage=stage,
                decision=decision,
                reason_code=reason_code,
                item=item,
                details=details,
                attempt=attempt,
                replacement_eligible=item.get("replacement_eligible"),
            ),
            path,
        )
    except Exception:
        return


def _safe_summarize(item, summarize_fn):
    """Isolate recoverable provider failures at candidate boundary; never fabricate a summary."""
    try:
        return summarize_fn(item)
    except (QuotaExceeded, TimeoutError, requests.exceptions.RequestException) as exc:
        identity = _publication_identity(item)
        reason_code = {
            QuotaExceeded: "provider_quota_exceeded",
            TimeoutError: "provider_timeout",
            requests.exceptions.RequestException: "provider_request_failure",
        }.get(type(exc), "provider_generation_failure")
        _runtime_telemetry_event(
            item,
            stage="summarization",
            decision="unavailable",
            reason_code=reason_code,
            details={"exception_type": type(exc).__name__, "exception": str(exc)[:500]},
        )
        print(f"[Editorial Gate] provider failure isolated candidate={identity[:120]} exception={type(exc).__name__}: {exc}", flush=True)
        item["_publication_blocked"] = True
        item["_summary_provider_failure"] = type(exc).__name__
        return None


def _summarize_selected(items, summarize_fn):
    workers = max(1, int(os.getenv("RADAR_SUMMARY_WORKERS", "1") or 1))
    if workers == 1 or len(items) <= 1:
        return [_safe_summarize(item, summarize_fn) for item in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as executor:
        return list(executor.map(lambda item: _safe_summarize(item, summarize_fn), items))

