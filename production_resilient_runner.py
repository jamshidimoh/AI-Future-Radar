"""Resilient production launcher.

Education is a separate scheduled product stream. If education cannot satisfy
its source contract, the news pipeline continues exactly once with education
explicitly disabled; the news orchestration is never rerun after completion.
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
import src.normal_publication_fallback as _normal_fallback  # noqa: E402
import src.production_publication_adapter as _publication_adapter  # noqa: E402

_ORIGINAL_FETCH_REFERENCE = educational_content._fetch_reference
_ORIGINAL_REWRITE_EDUCATION_PERSIAN = production_entrypoint._rewrite_education_persian
_ORIGINAL_PUBLISH_PRODUCTION_STORY = _publication_adapter.publish_production_story

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
            if "[Education Contract]" not in message and "[Education Source Gate]" not in message:
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
