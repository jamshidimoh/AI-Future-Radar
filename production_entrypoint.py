"""Canonical production entrypoint with four independent editorial lanes."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from src.editorial_quality_policy import (
    NORMAL_SCORE_FLOOR,
    PROTECTED_SCORE_FLOOR,
    news_language_ok,
    normal_score_allowed,
    persian_ratio,
    protected_score_allowed,
)
from src.logging_setup import configure_logging
from src.priority_people import is_substantive_priority_interview
from src.protected_editorial_lane import SPECIAL_MAX_PER_PERIOD, choose_additive_candidates
from src.state_io import StateCorruptionError, load_json_state
from src.technical_trend_lane import choose_technical_trend_candidate
from src.unified_editorial_selection import load_editorial_contract
from src.voices_perspectives_lane import MAX_VOICES_PER_PERIOD, choose_voices_candidate, is_voices_candidate

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
FEEDBACK_PATH = ROOT / "data" / "telegram_feedback.json"
CADENCE_PATH = ROOT / "data" / "publication_state.json"
EDITORIAL_CONTRACT = load_editorial_contract()
MAX_NORMAL_NEWS_PER_PERIOD = 3
MAX_MIND_IDEAS_VOICES_PER_PERIOD = SPECIAL_MAX_PER_PERIOD
MAX_TECHNICAL_TREND_PER_PERIOD = 1
MAX_VOICES_PERSPECTIVES_PER_PERIOD = MAX_VOICES_PER_PERIOD
NORMAL_RELATIVE_SCORE_GAP = 8.0
RANK_WINDOW = int(EDITORIAL_CONTRACT["candidate_window"])
PROTECTED_SUMMARY_SCORE_FLOOR = PROTECTED_SCORE_FLOOR
EDU_FIELDS = ("term_a_definition", "term_a_simple", "term_b_definition", "term_b_simple", "relationship", "example", "takeaway")
NEWS_FIELDS = ("title", "summary", "why_it_matters")
GUARD_REASON_ENV = "AI_RADAR_PUBLICATION_GUARD_REASON"
EDUCATION_WINDOWS_TEHRAN = ((5, 7, "morning"), (20, 7, "evening"))
TEHRAN = timezone(timedelta(hours=3, minutes=30))
STRATEGIC_ANALYTICAL_MAX_PER_PERIOD = 1
STRATEGIC_ANALYTICAL_CATEGORIES = {"future", "future_governance", "mind", "mind_cognition"}


def _load_cadence() -> dict:
    data = load_json_state(CADENCE_PATH, {}, label="publication cadence state")
    if not isinstance(data, dict):
        data = {}
    return {
        "run_number": int(data.get("run_number", 0)),
        "last_education_run": int(data.get("last_education_run", 0)),
        "last_education_slot": str(data.get("last_education_slot", "")),
        "last_published_news_score": data.get("last_published_news_score"),
        "last_published_normal_news_score": data.get("last_published_normal_news_score", data.get("last_published_news_score")),
    }


def _save_cadence(state: dict) -> None:
    CADENCE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tehran_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(TEHRAN)


def _education_slot(now: datetime | None = None) -> str | None:
    now = now or _tehran_now()
    for hour, _, name in EDUCATION_WINDOWS_TEHRAN:
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
        logger.error("Education language rewrite failed: %s", exc, exc_info=True)
    raise RuntimeError("[Education Language Gate] educational prose is not sufficiently Persian")


def _news_language_ok(item: dict) -> bool:
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    why = str(item.get("why_it_matters", ""))
    ok = news_language_ok(title, summary, why)
    if not ok:
        print("[News Publication Gate] blocked untranslated item: " f"title={persian_ratio(title):.2f} summary={persian_ratio(summary):.2f} why_it_matters={persian_ratio(why):.2f}", flush=True)
    return ok


def _is_mind_ideas_voices(item: dict) -> bool:
    return bool(
        item.get("mind_lane_selected")
        or item.get("protected_editorial_lane") == "mind_ideas_voices"
        or item.get("lane") == "mind_ideas_voices"
    )


def _is_technical_trend(item: dict) -> bool:
    return bool(item.get("technical_trend_lane_selected") or item.get("editorial_lane") == "technical_trend")


def _is_voices_perspectives(item: dict) -> bool:
    return bool(item.get("voices_perspectives_lane_selected") or item.get("editorial_lane") == "voices_perspectives")


def _item_final_score(item: dict) -> float:
    if _is_technical_trend(item):
        try:
            return float(item.get("technical_trend_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    if _is_mind_ideas_voices(item):
        try:
            return float(item.get("mind_editorial_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    if _is_voices_perspectives(item):
        try:
            return float(item.get("voices_perspectives_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
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


def _is_tier0_publication_candidate(item: dict) -> bool:
    return is_substantive_priority_interview(item) or bool(
        item.get("critical_ai_incident") and item.get("protected_slot")
    )


def _is_strategic_analytical_signal(item: dict) -> bool:
    classification = item.get("leader_signal_classification") or {}
    if not isinstance(classification, dict):
        return False
    if not (item.get("is_leader_watch") and classification.get("accepted") and classification.get("analytical") and classification.get("context")):
        return False
    category = str(item.get("category") or "").strip().casefold()
    if category not in STRATEGIC_ANALYTICAL_CATEGORIES:
        return False
    try:
        leader_priority = int(item.get("leader_priority", 0) or 0)
    except (TypeError, ValueError):
        leader_priority = 0
    if leader_priority < 8:
        return False
    try:
        source_tier = int(item.get("source_tier", 3) or 3)
    except (TypeError, ValueError):
        source_tier = 3
    if source_tier > 2:
        return False
    source_text = " ".join(str(item.get(key) or "").strip().casefold() for key in ("source", "source_name", "source_type", "source_domain"))
    return not any(marker in source_text for marker in ("reddit", "community"))


def _competitive_normal_candidates(candidates):
    candidates = list(candidates or [])
    regular = [
        x for x in candidates
        if not _is_mind_ideas_voices(x)
        and not _is_technical_trend(x)
        and not _is_voices_perspectives(x)
        and not x.get("_rank_is_tier0")
    ]
    protected = [x for x in candidates if x.get("_rank_is_tier0")]
    if not regular:
        return candidates
    scores = [float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0.0) for x in regular]
    best = max(scores)
    cutoff = max(float(NORMAL_SCORE_FLOOR), best - NORMAL_RELATIVE_SCORE_GAP)
    score_kept = [x for x in regular if float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0.0) >= cutoff]
    mission_targeted = [
        x for x in regular
        if str(x.get("mission_selection_reason") or "").startswith("mission_target:")
    ]
    score_kept_ids = {id(x) for x in score_kept}
    kept = score_kept + [x for x in mission_targeted if id(x) not in score_kept_ids]
    print(
        f"[Normal Competitive Gate] candidates={len(regular)} best={best:.2f} cutoff={cutoff:.2f} "
        f"gap={NORMAL_RELATIVE_SCORE_GAP:.1f} kept={len(kept)} dropped={len(regular)-len(kept)} "
        f"mission_targets_preserved={len(kept)-len(score_kept)}",
        flush=True,
    )
    return protected + kept


def _bound_runtime_candidates(candidates, max_posts: int, policy: dict):
    candidates = list(candidates or [])
    voices = [item for item in candidates if _is_voices_perspectives(item)][:MAX_VOICES_PERSPECTIVES_PER_PERIOD]
    technical = [item for item in candidates if _is_technical_trend(item)][:MAX_TECHNICAL_TREND_PER_PERIOD]
    mind = [item for item in candidates if _is_mind_ideas_voices(item)][:MAX_MIND_IDEAS_VOICES_PER_PERIOD]
    non_special = [
        item for item in candidates
        if not _is_mind_ideas_voices(item) and not _is_technical_trend(item) and not _is_voices_perspectives(item)
    ]
    protected_limit = max(0, int(policy.get("leader_protected_max", 2) or 0))
    normal_capacity = max(0, int(max_posts or 0))
    replacement_buffer = max(0, int(policy.get("replacement_buffer", EDITORIAL_CONTRACT.get("replacement_buffer", 0)) or 0))
    normal_limit = normal_capacity + replacement_buffer
    protected = []
    for item in non_special:
        if not item.get("protected_slot"):
            continue
        try:
            score = float(item.get("final_editorial_score", item.get("editorial_score", 0)) or 0)
        except (TypeError, ValueError):
            score = 0.0
        if score >= PROTECTED_SUMMARY_SCORE_FLOOR:
            protected.append(item)
        if len(protected) >= protected_limit:
            break
    normals = [item for item in non_special if item.get("normal_period_rank") is not None][:normal_limit]
    bounded = []
    seen = set()
    for item in protected + normals + technical + mind + voices:
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        bounded.append(item)
    print(
        f"[Selection Budget Guard] normal={len(normals)} protected={len(protected)} technical_trend={len(technical)} mind_ideas_voices={len(mind)} voices_perspectives={len(voices)} output={len(bounded)} normal_capacity={normal_capacity} normal_limit={normal_limit} technical_quota={MAX_TECHNICAL_TREND_PER_PERIOD} mind_quota={MAX_MIND_IDEAS_VOICES_PER_PERIOD} voices_quota={MAX_VOICES_PERSPECTIVES_PER_PERIOD}",
        flush=True,
    )
    return bounded


def main(*, skip_education: bool = False) -> int:
    configure_logging()
    import main as pipeline_module
    import period_ranked_pipeline as pipeline
    pipeline = cast(Any, pipeline)
    pipeline_module.NORMAL_SCORE_FLOOR = NORMAL_SCORE_FLOOR
    pipeline_module.PROTECTED_SUMMARY_SCORE_FLOOR = PROTECTED_SCORE_FLOOR

    from src.delivery_contract import DeliveryStatus, delivered, policy_blocked, transport_failed
    from src.educational_content import build_educational_item, commit_education_lesson
    from src.educational_telegram_style import format_educational_post
    from src.llm_router_light import call_llm_with_fallback, get_quality_chain
    from src.production_publication_adapter import publish_production_story
    from src.publication_contract import unique_candidates
    from src.telegram_feedback import ingest_from_env, load_feedback, register_post, save_feedback
    from src.telegram_single_delivery import send

    cadence = _load_cadence()
    run_number = cadence["run_number"] + 1
    now_tehran = _tehran_now()
    education_due, education_slot = _education_is_due(now_tehran, cadence.get("last_education_slot", ""))
    if skip_education:
        education_due = False
        education_slot = None
    previous_normal_score = cadence.get("last_published_normal_news_score")
    print(f"[Cadence] run={run_number} tehran={now_tehran.isoformat()} normal_news=ranked_1_plus_2 max_normal={MAX_NORMAL_NEWS_PER_PERIOD} technical_trend=independent max_technical={MAX_TECHNICAL_TREND_PER_PERIOD} mind_ideas_voices=independent max_mind={MAX_MIND_IDEAS_VOICES_PER_PERIOD} voices_perspectives=independent max_voices={MAX_VOICES_PERSPECTIVES_PER_PERIOD} education_due={education_due} education_slot={education_slot} previous_normal_score={previous_normal_score} last_any_news_score={cadence.get('last_published_news_score')}", flush=True)

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
            education_item = None
            print(f"[Education Source Gate] DEFERRED slot={education_slot} reason={exc}; news orchestration continues and slot remains due", flush=True)
            logger.error("Education source gate deferred: %s", exc, exc_info=True)

    original_select = pipeline.select_editorial

    def select_with_feedback(items, max_posts, max_per_source, max_per_type, policy):
        started = time.monotonic()
        for item in items:
            bonus = _feedback_bonus(store, item)
            item["audience_feedback_bonus"] = bonus
            item["editorial_score"] = round(float(item.get("editorial_score", 0) or 0) + bonus, 2)
        print(f"[Selection Timing] feedback items={len(items)} elapsed={time.monotonic() - started:.3f}s", flush=True)
        rank_started = time.monotonic()
        candidate_window = int(EDITORIAL_CONTRACT["candidate_window"])

        voices_candidates = choose_voices_candidate(
            items,
            existing_ids=set(),
            max_items=MAX_VOICES_PERSPECTIVES_PER_PERIOD,
        )
        voices_ids = {id(item) for item in voices_candidates}
        for item in voices_candidates:
            print(f"[Voices/Perspectives Selection] rank={item.get('voices_period_rank')} score={item.get('voices_perspectives_score')} source={item.get('source')} person={item.get('person_name') or item.get('watch_person') or item.get('leader')} title={str(item.get('title', ''))[:120]}", flush=True)

        normal_pool = [item for item in items if id(item) not in voices_ids and not is_voices_candidate(item)]
        normal_select_count = max(candidate_window, min(len(normal_pool), max_posts))
        normal_candidates = _competitive_normal_candidates(
            unique_candidates(original_select(normal_pool, normal_select_count, max_per_source, max_per_type, policy))
        )
        normal_ids = {id(item) for item in normal_candidates}

        mind_candidates = choose_additive_candidates(
            items,
            existing_ids=voices_ids | normal_ids,
            max_items=MAX_MIND_IDEAS_VOICES_PER_PERIOD,
        )
        mind_ids = {id(item) for item in mind_candidates}
        for item in mind_candidates:
            print(f"[Mind/Ideas/Voices Selection] rank={item.get('mind_period_rank')} score={item.get('mind_editorial_score')} normal_score={item.get('editorial_score', 0)} normal_rank=None title={str(item.get('title', ''))[:120]}", flush=True)

        technical_candidates = choose_technical_trend_candidate(
            items,
            existing_ids=voices_ids | normal_ids | mind_ids,
            max_items=MAX_TECHNICAL_TREND_PER_PERIOD,
        )
        for item in technical_candidates:
            print(f"[Technical Trend Selection] rank={item.get('technical_trend_period_rank')} score={item.get('technical_trend_score')} source={item.get('source')} title={str(item.get('title', ''))[:120]}", flush=True)

        candidates = unique_candidates(normal_candidates + technical_candidates + mind_candidates + voices_candidates)
        print(
            f"[Four Lane Selection] normal={len(normal_candidates)} technical_trend={len(technical_candidates)} mind_ideas_voices={len(mind_candidates)} voices_perspectives={len(voices_candidates)} technical_cap={MAX_TECHNICAL_TREND_PER_PERIOD} mind_cap={MAX_MIND_IDEAS_VOICES_PER_PERIOD} voices_cap={MAX_VOICES_PERSPECTIVES_PER_PERIOD} normal_score_floor=normal_only",
            flush=True,
        )
        print(f"[Selection Timing] original_select candidates={len(candidates)} candidate_window={candidate_window} elapsed={time.monotonic() - rank_started:.3f}s", flush=True)
        return ([education_item] if education_item else []) + _bound_runtime_candidates(candidates, max_posts=max_posts, policy=policy)

    original_summarize = pipeline.summarize_item
    render_state: dict[str, Any] = {"current_type": None, "current_item": None, "education_delivered": False, "normal_news_delivered_count": 0, "mind_ideas_voices_delivered_count": 0, "technical_trend_delivered_count": 0, "voices_perspectives_delivered_count": 0, "tier0_news_delivered_count": 0, "strategic_analytical_news_delivered_count": 0, "published_news_scores": [], "delivery_transport_failed": False}

    def summarize_with_education(item):
        if item.get("content_type") == "education":
            print(f"[Education Pipeline] ready for publication: lesson={item.get('education_id')}", flush=True)
            return {"_educational_ready": True}
        result = original_summarize(item)
        if result:
            item.update(result)
            if _is_technical_trend(item):
                item["final_editorial_score"] = float(item.get("technical_trend_score", 0) or 0)
                lane = "technical_trend"
            elif _is_mind_ideas_voices(item):
                item["final_editorial_score"] = float(item.get("mind_editorial_score", 0) or 0)
                lane = "mind_ideas_voices"
            elif _is_voices_perspectives(item):
                item["final_editorial_score"] = float(item.get("voices_perspectives_score", 0) or 0)
                lane = "voices_perspectives"
            else:
                item["final_editorial_score"] = _item_final_score(item)
                lane = "strategic_analytical" if _is_strategic_analytical_signal(item) else "normal"
            print(f"[Fallback] publishable candidate prepared lane={lane} global_rank={item.get('period_rank')} normal_rank={item.get('normal_period_rank')} mind_score={item.get('mind_editorial_score')} technical_score={item.get('technical_trend_score')} voices_score={item.get('voices_perspectives_score')} score={item.get('final_editorial_score')}: {str(item.get('title',''))[:120]}", flush=True)
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
                is_mind = _is_mind_ideas_voices(item)
                is_technical = _is_technical_trend(item)
                is_voices = _is_voices_perspectives(item)
                is_tier0 = _is_tier0_publication_candidate(item)
                is_strategic = _is_strategic_analytical_signal(item)
                if not is_mind and not is_technical and not is_voices and not is_tier0:
                    cadence["last_published_normal_news_score"] = score
                if is_mind:
                    render_state["mind_ideas_voices_delivered_count"] += 1
                elif is_technical:
                    render_state["technical_trend_delivered_count"] += 1
                elif is_voices:
                    render_state["voices_perspectives_delivered_count"] += 1
                elif is_tier0:
                    render_state["tier0_news_delivered_count"] += 1
                else:
                    render_state["normal_news_delivered_count"] += 1
                if is_strategic:
                    render_state["strategic_analytical_news_delivered_count"] += 1
                lane = "mind_ideas_voices" if is_mind else ("technical_trend" if is_technical else ("voices_perspectives" if is_voices else ("tier0" if is_tier0 else "normal")))
                print(f"[Publication Ledger] message_id={meta.get('message_id')} lane={lane} published_news_score={score} normal_baseline={cadence.get('last_published_normal_news_score')} global_rank={item.get('period_rank')} normal_rank={item.get('normal_period_rank')} mind_rank={item.get('mind_period_rank')} technical_rank={item.get('technical_trend_period_rank')} voices_rank={item.get('voices_period_rank')}", flush=True)
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
        is_mind = _is_mind_ideas_voices(story)
        is_technical = _is_technical_trend(story)
        is_voices = _is_voices_perspectives(story)
        priority_person = _is_tier0_publication_candidate(story)
        strategic_analytical = _is_strategic_analytical_signal(story)
        if is_voices:
            if render_state["voices_perspectives_delivered_count"] >= MAX_VOICES_PERSPECTIVES_PER_PERIOD:
                return policy_blocked("voices_perspectives_quota_exhausted")
            if not _news_language_ok(story):
                return policy_blocked("news_language_gate")
            score = _item_final_score(story)
            print(f"[Publication Policy] PUBLISH voices_perspectives voices_rank={story.get('voices_period_rank')} score={score} normal_floor=not_applied normal_rank=None independent_lane=true", flush=True)
            return delivered({"message_id": None})
        if is_mind:
            if render_state["mind_ideas_voices_delivered_count"] >= MAX_MIND_IDEAS_VOICES_PER_PERIOD:
                return policy_blocked("mind_ideas_voices_quota_exhausted")
            if not _news_language_ok(story):
                return policy_blocked("news_language_gate")
            score = _item_final_score(story)
            print(f"[Publication Policy] PUBLISH mind_ideas_voices mind_rank={story.get('mind_period_rank')} score={score} normal_floor=not_applied normal_rank=None independent_lane=true", flush=True)
            return delivered({"message_id": None})
        if is_technical:
            if render_state["technical_trend_delivered_count"] >= MAX_TECHNICAL_TREND_PER_PERIOD:
                return policy_blocked("technical_trend_quota_exhausted")
            if not _news_language_ok(story):
                return policy_blocked("news_language_gate")
            score = _item_final_score(story)
            print(f"[Publication Policy] PUBLISH technical_trend tech_rank={story.get('technical_trend_period_rank')} score={score} normal_floor=not_applied normal_rank=None independent_lane=true", flush=True)
            return delivered({"message_id": None})
        if strategic_analytical and render_state["strategic_analytical_news_delivered_count"] >= STRATEGIC_ANALYTICAL_MAX_PER_PERIOD:
            return policy_blocked("strategic_analytical_lane_exhausted")
        if not priority_person and render_state["normal_news_delivered_count"] >= MAX_NORMAL_NEWS_PER_PERIOD:
            return policy_blocked("normal_quota_exhausted")
        if not _news_language_ok(story):
            return policy_blocked("news_language_gate")
        score = _item_final_score(story)
        global_rank = int(story.get("period_rank", 999) or 999)
        normal_rank = story.get("normal_period_rank")
        normal_rank = int(normal_rank) if normal_rank is not None else None
        if priority_person:
            if not protected_score_allowed(score):
                return policy_blocked(f"tier0_score_policy_blocked:{score}<floor:{PROTECTED_SCORE_FLOOR}")
            print(f"[Publication Policy] PUBLISH TIER0 interview/quote global_rank={global_rank} tier0_rank={story.get('tier0_rank')} score={score} quality_floor={PROTECTED_SCORE_FLOOR} quota_exempt=true", flush=True)
            return delivered({"message_id": None})
        if normal_rank is None or normal_rank > RANK_WINDOW:
            return policy_blocked(f"normal_rank_outside_window:{normal_rank}")
        if strategic_analytical:
            print(f"[Publication Policy] PUBLISH STRATEGIC_ANALYTICAL normal_rank={normal_rank} score={score} ranking_floor=not_applied lane_cap={STRATEGIC_ANALYTICAL_MAX_PER_PERIOD} quota_counted=true", flush=True)
            return delivered({"message_id": None})
        baseline = previous_normal_score
        if not normal_news_policy_allowed(score, baseline, normal_rank):
            return policy_blocked(f"normal_score_policy_blocked:{score}<floor:{NORMAL_SCORE_FLOOR}")
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

    hooks = {"select_editorial": select_with_feedback, "summarize_item": summarize_with_education, "format_post": format_with_education, "mark_as_seen": mark_with_telegram, "send_to_telegram_safe": delivery_and_capture}
    try:
        pipeline.main(hooks=hooks)
    finally:
        globals()["_NEWS_PIPELINE_COMPLETED"] = True

    save_feedback(store, FEEDBACK_PATH)
    cadence["run_number"] = run_number
    _save_cadence(cadence)
    if education_due and not render_state["education_delivered"]:
        print(f"[Education Contract] deferred: educational Telegram post was not confirmed; slot={education_slot} remains due for retry", flush=True)
    print(f"[Production Contract] normal_news={render_state['normal_news_delivered_count']} normal_max={MAX_NORMAL_NEWS_PER_PERIOD} technical_trend={render_state['technical_trend_delivered_count']} technical_max={MAX_TECHNICAL_TREND_PER_PERIOD} mind_ideas_voices={render_state['mind_ideas_voices_delivered_count']} mind_max={MAX_MIND_IDEAS_VOICES_PER_PERIOD} voices_perspectives={render_state['voices_perspectives_delivered_count']} voices_max={MAX_VOICES_PERSPECTIVES_PER_PERIOD} tier0_news={render_state['tier0_news_delivered_count']} strategic_analytical={render_state['strategic_analytical_news_delivered_count']} strategic_max={STRATEGIC_ANALYTICAL_MAX_PER_PERIOD} normal_score_floor={NORMAL_SCORE_FLOOR} special_lanes_score_floor=not_applied education={'confirmed' if render_state['education_delivered'] else ('deferred' if education_due else 'not_due')}", flush=True)
    print(f"[Telegram Feedback] stored_messages={len(store.get('messages', {}))}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StateCorruptionError as exc:
        logger.error("[STATE] %s", exc, exc_info=True)
        raise SystemExit(1) from exc
