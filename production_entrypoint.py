"""Production entrypoint with explicit normal-news policy and resilient education cadence."""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.editorial_quality_policy import news_language_ok, normal_score_allowed, persian_ratio
from src.priority_people import is_substantive_priority_interview

ROOT = Path(__file__).resolve().parent
FEEDBACK_PATH = ROOT / "data" / "telegram_feedback.json"
CADENCE_PATH = ROOT / "data" / "publication_state.json"
MAX_NORMAL_NEWS_PER_PERIOD = 3
RANK_WINDOW = 4
EDU_FIELDS = ("term_a_definition", "term_a_simple", "term_b_definition", "term_b_simple", "relationship", "example", "takeaway")
NEWS_FIELDS = ("title", "summary", "why_it_matters")
GUARD_REASON_ENV = "AI_RADAR_PUBLICATION_GUARD_REASON"
EDUCATION_WINDOWS_TEHRAN = ((5, 7, "morning"), (20, 7, "evening"))
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def _load_cadence() -> dict:
    try:
        data = json.loads(CADENCE_PATH.read_text(encoding="utf-8"))
        return {
            "run_number": int(data.get("run_number", 0)),
            "last_education_run": int(data.get("last_education_run", 0)),
            "last_education_slot": str(data.get("last_education_slot", "")),
            "last_published_news_score": data.get("last_published_news_score"),
            "last_published_normal_news_score": data.get("last_published_normal_news_score", data.get("last_published_news_score")),
        }
    except Exception:
        return {"run_number": 0, "last_education_run": 0, "last_education_slot": "", "last_published_news_score": None, "last_published_normal_news_score": None}


def _save_cadence(state: dict) -> None:
    CADENCE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tehran_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(TEHRAN)


def _education_slot(now: datetime | None = None) -> str | None:
    """Return the current education slot only during a scheduled publication window.

    A generous one-hour window after the nominal cron time tolerates GitHub Actions
    queueing without allowing the following news cycle to become an education run.
    """
    now = now or _tehran_now()
    for hour, minute, name in EDUCATION_WINDOWS_TEHRAN:
        start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        end = now.replace(hour=hour + 1, minute=30, second=0, microsecond=0)
        if start <= now <= end:
            return f"{now.date().isoformat()}:{name}"
    return None


def _education_is_due(now: datetime | None, last_slot: str) -> tuple[bool, str | None]:
    slot = _education_slot(now)
    return bool(slot and slot != last_slot), slot


def _record_normalized_score(record: dict) -> float:
    counts = record.get("reaction_counts") or {}
    weights = {"👍": 1.0, "❤️": 1.2, "🔥": 1.5, "🤔": -0.8, "💡": 1.3}
    reaction_score = sum(int(counts.get(emoji, 0)) * weight for emoji, weight in weights.items())
    comments = int(record.get("comment_count", 0) or 0)
    engagement = (reaction_score * 0.8) + (min(comments, 50) * 0.35)
    denominator = max(1, sum(int(v) for v in counts.values()) + comments)
    return max(-1.0, min(1.0, engagement / denominator))


def _profile_score(store: dict, key: str, value: str) -> float:
    scores = [_record_normalized_score(record) for record in (store.get("messages") or {}).values() if record.get(key) == value]
    return max(-1.0, min(1.0, sum(scores) / len(scores))) if scores else 0.0


def _feedback_bonus(store: dict, item: dict) -> float:
    signals = []
    for key in ("source", "content_type", "category", "leader"):
        value = str(item.get(key) or item.get("watch_person") or "").strip()
        if value:
            signals.append(_profile_score(store, key, value))
    return round(max(-5.0, min(5.0, (sum(signals) / len(signals)) * 5.0)), 2) if signals else 0.0


def _persian_ratio(text: str) -> float:
    return persian_ratio(text)


def _rewrite_education_persian(item: dict, llm_call, providers) -> dict:
    payload = {k: str(item.get(k, "")) for k in EDU_FIELDS}
    prompt = """تو ویراستار نهایی یک رسانه تخصصی فارسی درباره هوش مصنوعی و فناوری هستی.
این متن آموزشی را برای انتشار در Telegram به فارسی حرفه‌ای بازنویسی کن.
قواعد قطعی: حداقل ۷۰ درصد متن فارسی باشد؛ معنا، عدد و ادعا تغییر نکند؛ نام افراد/شرکت‌ها/محصولات/مدل‌ها Latin رسمی بماند؛ اصطلاحات تخصصی ضروری English رسمی بمانند؛ آوانویسی فارسی نام خاص ممنوع؛ خروجی فقط JSON معتبر با دقیقاً هفت کلید ورودی باشد."""
    raw, provider = llm_call(prompt, json.dumps(payload, ensure_ascii=False), providers=providers)
    try:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1]).strip()
        start, end = text.find("{"), text.rfind("}")
        result = json.loads(text[start:end + 1] if start >= 0 and end > start else text)
        if isinstance(result, dict) and all(str(result.get(k, "")).strip() for k in EDU_FIELDS):
            candidate = dict(item)
            candidate.update({k: str(result[k]).strip() for k in EDU_FIELDS})
            ratios = [_persian_ratio(candidate[k]) for k in EDU_FIELDS]
            if min(ratios) >= 0.70:
                candidate["_language_provider"] = provider or "editorial QA"
                return candidate
            print(f"[Education Language Gate] rejected min_ratio={min(ratios):.2f}", flush=True)
    except Exception as exc:
        print(f"[Education Language Gate] rewrite failed: {exc}", flush=True)
    raise RuntimeError("[Education Language Gate] educational prose is not sufficiently Persian")


def _news_language_ok(item: dict) -> bool:
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    why = str(item.get("why_it_matters", ""))
    ok = news_language_ok(title, summary, why)
    if not ok:
        print("[News Publication Gate] blocked untranslated item: " f"title={persian_ratio(title):.2f} summary={persian_ratio(summary):.2f} why_it_matters={persian_ratio(why):.2f}", flush=True)
    return ok


def _item_final_score(item: dict) -> float:
    for key in ("final_editorial_score", "leader_story_score", "mission_score", "editorial_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
            if value:
                return value
        except (TypeError, ValueError):
            pass
    return 0.0


def normal_news_policy_allowed(score: float, previous_normal_score: float | None, normal_rank: int | None) -> bool:
    if normal_rank is None or normal_rank > RANK_WINDOW:
        return False
    return normal_score_allowed(float(score), previous_normal_score)


def main(*, skip_education: bool = False) -> int:
    import period_ranked_pipeline as pipeline
    from educational_content import build_educational_item, commit_education_lesson
    from educational_telegram_style import format_educational_post
    from llm_router_light import call_llm_with_fallback, get_quality_chain
    from telegram_feedback import ingest_from_env, load_feedback, register_post, save_feedback
    from src.delivery_contract import DeliveryStatus, delivered, policy_blocked, transport_failed
    from src.production_publication_adapter import publish_production_story
    from src.publication_contract import unique_candidates
    from telegram_single_delivery import send

    cadence = _load_cadence()
    run_number = cadence["run_number"] + 1
    now_tehran = _tehran_now()
    education_due, education_slot = _education_is_due(now_tehran, cadence.get("last_education_slot", ""))
    if skip_education:
        education_due = False
        education_slot = None
    previous_normal_score = cadence.get("last_published_normal_news_score")
    print(f"[Cadence] run={run_number} tehran={now_tehran.isoformat()} normal_news=ranked_1_plus_2 max_normal={MAX_NORMAL_NEWS_PER_PERIOD} education_due={education_due} education_slot={education_slot} education_windows=05:17,20:47 news_windows=05:17,10:47,13:47,17:47,20:47,22:47 previous_normal_score={previous_normal_score} last_any_news_score={cadence.get('last_published_news_score')}", flush=True)

    store = load_feedback(FEEDBACK_PATH)
    changed = ingest_from_env(FEEDBACK_PATH)
    if changed:
        store = load_feedback(FEEDBACK_PATH)
    print(f"[Telegram Feedback] updates_ingested={changed}", flush=True)

    education_item = None
    if education_due:
        try:
            education_item = build_educational_item()
            if not education_item:
                raise RuntimeError("no educational item could be built")
            ratios = [_persian_ratio(str(education_item.get(k, ""))) for k in EDU_FIELDS]
            if min(ratios) >= 0.70:
                education_item["_language_provider"] = "source-validated"
                print(f"[Education Language Gate] source_validated min_ratio={min(ratios):.2f}; rewrite skipped", flush=True)
            else:
                education_item = _rewrite_education_persian(education_item, call_llm_with_fallback, get_quality_chain())
            print(f"[Education] REQUIRED lesson={education_item.get('education_id')}/{education_item.get('education_total')} slot={education_slot}", flush=True)
        except Exception as exc:
            # A source outage must not fail or consume the educational slot.
            education_item = None
            print(f"[Education Source Gate] DEFERRED slot={education_slot} reason={exc}; news orchestration continues and slot remains due", flush=True)

    original_select = pipeline.select_editorial

    def select_with_feedback(items, max_posts, max_per_source, max_per_type, policy):
        started = time.monotonic()
        for item in items:
            bonus = _feedback_bonus(store, item)
            item["audience_feedback_bonus"] = bonus
            item["editorial_score"] = round(float(item.get("editorial_score", 0) or 0) + bonus, 2)
        print(f"[Selection Timing] feedback items={len(items)} elapsed={time.monotonic() - started:.3f}s", flush=True)
        rank_started = time.monotonic()
        candidates = unique_candidates(original_select(items, max(4, min(len(items), max_posts)), max_per_source, max_per_type, policy))
        print(f"[Selection Timing] original_select candidates={len(candidates)} elapsed={time.monotonic() - rank_started:.3f}s", flush=True)
        return ([education_item] if education_item else []) + candidates

    original_summarize = pipeline.summarize_item
    render_state = {"current_type": None, "current_item": None, "education_delivered": False, "normal_news_delivered_count": 0, "tier0_news_delivered_count": 0, "published_news_scores": [], "delivery_transport_failed": False}

    def summarize_with_education(item):
        if item.get("content_type") == "education":
            print(f"[Education Pipeline] ready for publication: lesson={item.get('education_id')}", flush=True)
            return {"_educational_ready": True}
        result = original_summarize(item)
        if result:
            item.update(result)
            item["final_editorial_score"] = _item_final_score(item)
            print(f"[Fallback] publishable candidate prepared global_rank={item.get('period_rank')} normal_rank={item.get('normal_period_rank')} score={item.get('final_editorial_score')}: {str(item.get('title',''))[:120]}", flush=True)
            return result
        item["_publication_blocked"] = True
        print(f"[Fallback] translation/QA failed; candidate blocked: {str(item.get('title',''))[:120]}", flush=True)
        return None

    original_format_post = pipeline.format_post

    def format_with_education(item, source_name, link, **kwargs):
        render_state["current_type"] = item.get("content_type")
        render_state["current_item"] = item
        return format_educational_post(item) if item.get("content_type") == "education" else original_format_post(item, source_name, link, **kwargs)

    original_mark = pipeline.mark_as_seen
    last_delivery = {"outcome": None, "meta": None}

    def _ledger(story, outcome):
        meta = outcome.as_dict()
        item = story
        if meta.get("message_id") is not None:
            item["telegram_chat_id"] = meta.get("chat_id")
            item["telegram_message_id"] = meta.get("message_id")
            if item.get("content_type") == "education":
                education_id = int(item.get("education_id", 0) or 0)
                item["publication_identity"] = f"education:{education_id}"
                item["title"] = item.get("title") or f"Education lesson {education_id}"
            register_post(store, meta, item)
            if item.get("content_type") != "education":
                score = _item_final_score(item)
                render_state["published_news_scores"].append(score)
                cadence["last_published_news_score"] = score
                if not is_substantive_priority_interview(item):
                    cadence["last_published_normal_news_score"] = score
                if is_substantive_priority_interview(item):
                    render_state["tier0_news_delivered_count"] += 1
                else:
                    render_state["normal_news_delivered_count"] += 1
                print(f"[Publication Ledger] message_id={meta.get('message_id')} published_news_score={score} normal_baseline={cadence.get('last_published_normal_news_score')} global_rank={item.get('period_rank')} normal_rank={item.get('normal_period_rank')} tier0={is_substantive_priority_interview(item)}", flush=True)
            else:
                render_state["education_delivered"] = True

    def mark_with_telegram(item, seen_hashes, seen_signatures, source_history=None):
        outcome = last_delivery.get("outcome")
        if outcome is not None and outcome.message_id is not None:
            item["telegram_chat_id"] = outcome.chat_id
            item["telegram_message_id"] = outcome.message_id
        if item.get("content_type") == "education" and outcome is not None and outcome.message_id is not None:
            commit_education_lesson(int(item.get("education_id", 0)))
            cadence["last_education_run"] = run_number
            cadence["last_education_slot"] = education_slot or f"run:{run_number}"
            return item
        return original_mark(item, seen_hashes, seen_signatures, source_history)

    def policy(story):
        current_type = story.get("content_type")
        if render_state["delivery_transport_failed"]:
            return transport_failed("telegram_transport_unavailable", retryable=False)
        if current_type == "education":
            return delivered({"message_id": None})
        priority_person = is_substantive_priority_interview(story)
        if not priority_person and render_state["normal_news_delivered_count"] >= MAX_NORMAL_NEWS_PER_PERIOD:
            return policy_blocked("normal_quota_exhausted")
        if not _news_language_ok(story):
            return policy_blocked("news_language_gate")
        score = _item_final_score(story)
        global_rank = int(story.get("period_rank", 999) or 999)
        normal_rank = story.get("normal_period_rank")
        normal_rank = int(normal_rank) if normal_rank is not None else None
        if priority_person:
            print(f"[Publication Policy] PUBLISH TIER0 interview/quote global_rank={global_rank} tier0_rank={story.get('tier0_rank')} score={score} quota_exempt=true", flush=True)
            return delivered({"message_id": None})
        if normal_rank is None or normal_rank > RANK_WINDOW:
            return policy_blocked(f"normal_rank_outside_window:{normal_rank}")
        baseline = previous_normal_score
        allowed = render_state["normal_news_delivered_count"] < MAX_NORMAL_NEWS_PER_PERIOD and normal_news_policy_allowed(score, baseline, normal_rank)
        if not allowed:
            return policy_blocked(f"normal_score_policy_blocked:{score}<={previous_normal_score}")
        print(f"[Publication Policy] PUBLISH normal_rank={normal_rank} score={score} previous_normal={previous_normal_score}", flush=True)
        return delivered({"message_id": None})

    def transport(story):
        text = story.get("_rendered_text", "")
        image_url = story.get("_rendered_image_url", "")
        source_link = str(story.get("link") or story.get("url") or "")
        os.environ.pop(GUARD_REASON_ENV, None)
        return send(text, image_url=image_url, source_link=source_link)

    def delivery_and_capture(text, image_url="", source_link=""):
        item = render_state.get("current_item") or {}
        item["_rendered_text"] = text
        item["_rendered_image_url"] = image_url
        if source_link:
            item["link"] = source_link
        outcome = publish_production_story(item, policy=policy, transport=transport, ledger=_ledger)
        last_delivery["outcome"] = outcome
        last_delivery["meta"] = outcome.as_dict()
        if outcome.status in {DeliveryStatus.DELIVERY_FAILED_RETRYABLE, DeliveryStatus.DELIVERY_FAILED_PERMANENT}:
            render_state["delivery_transport_failed"] = True
            print(f"[Telegram Delivery] transport failure; stopping further publication attempts reason={outcome.reason}", flush=True)
        elif outcome.status is not DeliveryStatus.DELIVERED:
            print(f"[Publication Contract] candidate rejected reason={outcome.reason}; continuing to next ranked candidate", flush=True)
        return outcome

    hooks = {
        "select_editorial": select_with_feedback,
        "summarize_item": summarize_with_education,
        "format_post": format_with_education,
        "mark_as_seen": mark_with_telegram,
        "send_to_telegram_safe": delivery_and_capture,
    }
    try:
        pipeline.main(hooks=hooks)
    finally:
        globals()["_NEWS_PIPELINE_COMPLETED"] = True

    save_feedback(store, FEEDBACK_PATH)
    cadence["run_number"] = run_number
    _save_cadence(cadence)
    if education_due and not render_state["education_delivered"]:
        print(f"[Education Contract] deferred: educational Telegram post was not confirmed; slot={education_slot} remains due for retry", flush=True)
    print(f"[Production Contract] normal_news={render_state['normal_news_delivered_count']} normal_max={MAX_NORMAL_NEWS_PER_PERIOD} tier0_news={render_state['tier0_news_delivered_count']} tier0_quota_exempt=true education={'confirmed' if render_state['education_delivered'] else ('deferred' if education_due else 'not_due')}", flush=True)
    print(f"[Telegram Feedback] stored_messages={len(store.get('messages', {}))}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
