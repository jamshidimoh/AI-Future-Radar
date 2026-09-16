"""Canonical production entrypoint with separate normal and Mind/Ideas/Voices lanes."""
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

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
FEEDBACK_PATH = ROOT / "data" / "telegram_feedback.json"
CADENCE_PATH = ROOT / "data" / "publication_state.json"
EDITORIAL_CONTRACT = load_editorial_contract()
MAX_NORMAL_NEWS_PER_PERIOD = 3
MAX_MIND_IDEAS_VOICES_PER_PERIOD = SPECIAL_MAX_PER_PERIOD
MAX_TECHNICAL_TREND_PER_PERIOD = 1
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