"""Source priority rules for deep, evidence-first Pioneer intelligence."""

from strategic_signal import strategic_forecast_score

SOURCE_WEIGHTS = {
    "full_paper": 1.00,
    "journal": 1.00,
    "full_transcript": 0.95,
    "technical_report": 0.90,
    "whitepaper": 0.90,
    "open_letter": 0.85,
    "university_talk": 0.82,
    "conference_talk": 0.80,
    "long_form_article": 0.72,
    "reputable_interview": 0.68,
    "news_report": 0.45,
    "social_post": 0.20,
}

TRIGGER_ONLY_TYPES = {"social_post", "short_clip", "headline_only"}

PRIORITY_CHANNELS = {
    "Lex Fridman Podcast": 0.95,
    "Dwarkesh Patel": 0.95,
    "No Priors Podcast": 0.90,
    "Sean Carroll's Mindscape": 0.88,
}


def source_weight(item: dict) -> float:
    source_type = str(item.get("source_format") or item.get("evidence_type") or "news_report").strip().lower()
    return float(SOURCE_WEIGHTS.get(source_type, 0.40))


def enrich_source_priority(item: dict) -> dict:
    out = dict(item)
    out["deep_source_weight"] = round(source_weight(out), 3)
    out["trigger_only"] = str(out.get("source_format") or "").strip().lower() in TRIGGER_ONLY_TYPES
    channel = str(out.get("source") or "").strip()
    out["priority_transcript_source"] = channel in PRIORITY_CHANNELS

    # Strategic importance is computed here so every mission_score() path consumes
    # it, including items discovered outside the explicit leader watchlist.
    strategic_score = strategic_forecast_score(out)
    out["strategic_forecast_bonus"] = round(min(18.0, strategic_score * 0.60), 2)
    out["signal_score"] = float(out.get("signal_score", 0) or 0) + out["strategic_forecast_bonus"]
    return out
