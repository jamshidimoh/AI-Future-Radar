"""Resilient production launcher.

Education is a separate scheduled product stream. If education cannot satisfy
its source or language contract, the news pipeline continues exactly once with
education explicitly disabled; the news orchestration is never rerun after completion.
"""
from __future__ import annotations

import faulthandler
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import educational_content  # noqa: E402
import production_entrypoint  # noqa: E402
import main as _pipeline  # noqa: E402
import src.normal_publication_fallback as _normal_fallback  # noqa: E402
import src.production_publication_adapter as _publication_adapter  # noqa: E402

_ORIGINAL_FETCH_REFERENCE = educational_content._fetch_reference
_ORIGINAL_REWRITE_EDUCATION_PERSIAN = production_entrypoint._rewrite_education_persian
_ORIGINAL_PUBLISH_PRODUCTION_STORY = _publication_adapter.publish_production_story
_ORIGINAL_PROTECTED_LEADER_INTERVIEW = _pipeline._is_protected_leader_interview

DEFAULT_WATCHDOG_MINUTES = 22


def _watchdog_minutes() -> int:
    raw = os.getenv("RADAR_WATCHDOG_MINUTES", str(DEFAULT_WATCHDOG_MINUTES)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_WATCHDOG_MINUTES
    return max(1, value)


def _publish_production_story_with_fallback(story, *, policy, transport, ledger):
    fallback_policy, tracked_ledger = _normal_fallback.wrap_policy(
        policy,
        ledger,
        rank_window=production_entrypoint.RANK_WINDOW,
    )
    return _ORIGINAL_PUBLISH_PRODUCTION_STORY(
        story,
        policy=fallback_policy,
        transport=transport,
        ledger=tracked_ledger,
    )


_publication_adapter.publish_production_story = _publish_production_story_with_fallback


def _fetch_reference_with_canonical_year(url: str):
    excerpt, year = _ORIGINAL_FETCH_REFERENCE(url)
    normalized = str(url or "").lower().rstrip("/")
    if year is None and normalized == "https://hai.stanford.edu/ai-index/2026-ai-index-report":
        year = 2026
        print(f"[Education Source Gate] canonical-year override year=2026 url={url}", flush=True)
    return excerpt, year


def _rewrite_education_only_if_needed(item: dict, llm_call, providers) -> dict:
    ratios = [production_entrypoint._persian_ratio(str(item.get(k, ""))) for k in production_entrypoint.EDU_FIELDS]
    minimum = min(ratios) if ratios else 0.0
    if minimum >= 0.70:
        item = dict(item)
        item["_language_provider"] = "source-validated"
        print(f"[Education Language Gate] source_validated min_ratio={minimum:.2f}; rewrite skipped", flush=True)
        return item
    return _ORIGINAL_REWRITE_EDUCATION_PERSIAN(item, llm_call, providers)


def _has_explicit_interview_evidence(item: dict) -> bool:
    """Require evidence of interview-style content before granting protected routing."""
    explicit = item.get("interview_signal") or item.get("interview_format") or item.get("is_interview")
    if explicit is True:
        return True
    text = " ".join(str(item.get(k) or "") for k in ("title", "summary", "description")).lower()
    terms = (
        "interview", "conversation", "fireside", "q&a", "question and answer",
        "talk with", "talks with", "speaks with", "in conversation", "sits down with",
        "مصاحبه", "گفتگو", "گفت‌وگو", "پرسش و پاسخ"
    )
    return any(term in text for term in terms)


def _protected_leader_interview_with_evidence(item) -> bool:
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    if not leader:
        return False
    watch = bool(item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("_named_leader_interview"))
    if not watch:
        return False
    source = str(item.get("source") or item.get("source_name") or "").lower()
    url = str(item.get("canonical_url") or item.get("link") or item.get("url") or "").lower()
    news_aggregator = "google news" in source or "news.google.com" in url or "/rss/articles/" in url
    if news_aggregator and not _has_explicit_interview_evidence(item):
        return False
    return bool(_ORIGINAL_PROTECTED_LEADER_INTERVIEW(item) and _has_explicit_interview_evidence(item))


_pipeline._is_protected_leader_interview = _protected_leader_interview_with_evidence


def _publish_education_after_news(run_number: int) -> bool:
    from educational_content import build_educational_item, commit_education_lesson
    from educational_telegram_style import format_educational_post
    from llm_router_light import call_llm_with_fallback, get_quality_chain
    from telegram_feedback import load_feedback, register_post, save_feedback
    from telegram_single_delivery import send
    from src.education_production_fallback import publish_required_education

    feedback_path = production_entrypoint.FEEDBACK_PATH
    cadence = production_entrypoint._load_cadence()
    try:
        item = build_educational_item()
        if not item:
            return False
        item = _rewrite_education_only_if_needed(item, call_llm_with_fallback, get_quality_chain())
        return publish_required_education(
            run_number=run_number,
            feedback_path=feedback_path,
            cadence=cadence,
            rewrite_fn=lambda x: x,
            fetch_builder=lambda: item,
            commit_lesson=commit_education_lesson,
            format_post=format_educational_post,
            send=send,
            load_feedback=load_feedback,
            register_post=register_post,
            save_feedback=save_feedback,
        )
    except Exception as exc:
        print(f"[Education Publication] independent fallback failed: {exc}", flush=True)
        return False
    finally:
        production_entrypoint._save_cadence(cadence)


def main() -> int:
    _normal_fallback._NORMAL_DELIVERED = 0
    watchdog_seconds = _watchdog_minutes() * 60
    faulthandler.dump_traceback_later(watchdog_seconds, exit=False, file=sys.stderr)
    educational_content._fetch_reference = _fetch_reference_with_canonical_year
    production_entrypoint._rewrite_education_persian = _rewrite_education_only_if_needed

    try:
        try:
            return production_entrypoint.main()
        except RuntimeError as exc:
            message = str(exc)
            education_error = (
                "[Education Contract]" in message
                or "[Education Source Gate]" in message
                or "[Education Language Gate]" in message
            )
            if not education_error:
                raise

            if getattr(production_entrypoint, "_NEWS_PIPELINE_COMPLETED", False):
                print(f"[Education Resilience] {message}; news pipeline already completed, publishing education independently", flush=True)
                run_number = production_entrypoint._load_cadence().get("run_number", 0)
                if _publish_education_after_news(int(run_number)):
                    print("[Education Resilience] independent education publication confirmed", flush=True)
                    return 0
                print("[Education Resilience] independent education publication failed", flush=True)
                return 1

            print(f"[Education Resilience] {message}; continuing news once with education disabled", flush=True)
            return production_entrypoint.main(skip_education=True)
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    raise SystemExit(main())
