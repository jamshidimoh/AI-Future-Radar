"""Resilient production launcher.

Education is a separate scheduled product stream. If education cannot satisfy
its source or language contract, the news pipeline continues exactly once with
education explicitly disabled; the news orchestration is never rerun after completion.
"""
from __future__ import annotations

import faulthandler
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import educational_content  # noqa: E402
import production_entrypoint  # noqa: E402
import src.normal_publication_fallback as _normal_fallback  # noqa: E402
import src.production_publication_adapter as _publication_adapter  # noqa: E402

_ORIGINAL_FETCH_REFERENCE = educational_content._fetch_reference
_ORIGINAL_SOURCE_CANDIDATES = educational_content._source_candidates
_ORIGINAL_REWRITE_EDUCATION_PERSIAN = production_entrypoint._rewrite_education_persian
_ORIGINAL_PUBLISH_PRODUCTION_STORY = _publication_adapter.publish_production_story

DEFAULT_WATCHDOG_MINUTES = 22
EDUCATION_LANGUAGE_MIN_RATIO = 0.70
EDUCATION_WINDOWS_TEHRAN = (6, 20)
LESSON_41_CURRENT_SOURCES = [
    {
        "name": "Anthropic: Demystifying evals for AI agents",
        "url": "https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents",
        "year": 2026,
    },
    {
        "name": "OpenAI Academy: Workspace agents",
        "url": "https://openai.com/academy/workspace-agents/",
        "year": 2026,
    },
]


def _watchdog_minutes() -> int:
    raw = os.getenv("RADAR_WATCHDOG_MINUTES", str(DEFAULT_WATCHDOG_MINUTES)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_WATCHDOG_MINUTES
    return max(1, value)


def _education_is_due_by_tehran_window(now: datetime | None, last_slot: str) -> tuple[bool, str | None]:
    """Return the education due state using the same tuple contract as production_entrypoint.

    Education is eligible only in the 06:xx and 20:xx Tehran windows. The slot
    identity prevents a manual retrigger from publishing the same lesson twice
    inside one window while allowing both intended daily windows.
    """
    now = now or datetime.now(ZoneInfo("Asia/Tehran"))
    slot = None
    if now.hour == 6:
        slot = f"{now.date().isoformat()}:morning"
    elif now.hour == 20:
        slot = f"{now.date().isoformat()}:evening"
    return bool(slot and slot != str(last_slot or "")), slot


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


def _source_candidates_with_current_overrides(lesson: dict):
    candidates = _ORIGINAL_SOURCE_CANDIDATES(lesson)
    lesson_id = int(lesson.get("id", 0) or 0)
    if lesson_id != 41:
        return candidates
    stale_urls = {
        "https://www.anthropic.com/research/building-effective-agents",
        "https://platform.openai.com/docs/guides/agents",
    }
    filtered = [x for x in candidates if str(x.get("url", "")).rstrip("/") not in {u.rstrip("/") for u in stale_urls}]
    filtered.extend(LESSON_41_CURRENT_SOURCES)
    print("[Education Source Gate] lesson=41 current-source override enabled", flush=True)
    return filtered


def _parse_education_json(raw):
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1] if start >= 0 and end > start else text)


def _education_language_retry(item: dict, llm_call, providers) -> dict:
    """Retry only the Persian-language rewrite; never relax the 70% gate."""
    payload = {k: str(item.get(k, "")) for k in production_entrypoint.EDU_FIELDS}
    prompt = """این متن آموزشی برای انتشار در یک رسانه تخصصی فارسی آماده شده اما بازنویسی قبلی از حداقل نسبت فارسی عبور نکرده است.
آن را دوباره و دقیق‌تر به فارسی حرفه‌ای بازنویسی کن.
قواعد قطعی:
- حداقل ۷۰٪ نویسه‌های هر یک از هفت فیلد باید فارسی باشد.
- معنا، اعداد، نام منابع و ادعاها را تغییر نده.
- نام افراد، شرکت‌ها، محصولات و مدل‌ها را فقط به شکل رسمی Latin نگه دار.
- فقط اصطلاحات تخصصی ضروری می‌توانند English باشند؛ جمله‌بندی و توضیح باید فارسی باشد.
- هیچ آوانویسی فارسی برای نام خاص یا اصطلاح تخصصی نساز.
- طول، ساختار معنایی و محتوای علمی را حفظ کن؛ فقط زبان را فارسی‌تر و روان‌تر کن.
- خروجی فقط JSON معتبر با دقیقاً همین هفت کلید باشد.
"""
    raw, provider = llm_call(prompt, json.dumps(payload, ensure_ascii=False), providers=providers)
    result = _parse_education_json(raw)
    if not isinstance(result, dict) or not all(str(result.get(k, "")).strip() for k in production_entrypoint.EDU_FIELDS):
        raise RuntimeError("[Education Language Gate] retry returned invalid JSON")
    candidate = dict(item)
    candidate.update({k: str(result[k]).strip() for k in production_entrypoint.EDU_FIELDS})
    ratios = [production_entrypoint._persian_ratio(candidate[k]) for k in production_entrypoint.EDU_FIELDS]
    minimum = min(ratios) if ratios else 0.0
    if minimum < EDUCATION_LANGUAGE_MIN_RATIO:
        raise RuntimeError(f"[Education Language Gate] retry rejected min_ratio={minimum:.2f}")
    candidate["_language_provider"] = provider or "editorial QA retry"
    print(f"[Education Language Gate] retry accepted min_ratio={minimum:.2f}", flush=True)
    return candidate


def _rewrite_education_only_if_needed(item: dict, llm_call, providers) -> dict:
    ratios = [production_entrypoint._persian_ratio(str(item.get(k, ""))) for k in production_entrypoint.EDU_FIELDS]
    minimum = min(ratios) if ratios else 0.0
    if minimum >= EDUCATION_LANGUAGE_MIN_RATIO:
        item = dict(item)
        item["_language_provider"] = "source-validated"
        print(f"[Education Language Gate] source_validated min_ratio={minimum:.2f}; rewrite skipped", flush=True)
        return item
    try:
        return _ORIGINAL_REWRITE_EDUCATION_PERSIAN(item, llm_call, providers)
    except RuntimeError as exc:
        if "[Education Language Gate]" not in str(exc):
            raise
        print("[Education Language Gate] first rewrite failed; running one bounded Persian-only retry", flush=True)
        return _education_language_retry(item, llm_call, providers)


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
    educational_content._source_candidates = _source_candidates_with_current_overrides
    production_entrypoint._rewrite_education_persian = _rewrite_education_only_if_needed
    production_entrypoint._education_is_due = _education_is_due_by_tehran_window

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
