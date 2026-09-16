"""Independent technical-trend editorial lane for AI architecture and infrastructure.

The lane is intentionally independent from both Normal News and Mind/Ideas/Voices.
It selects at most one technically substantive, current, high-value item from the
full discovery set. It never uses NORMAL_SCORE_FLOOR and does not consume the
Normal or Mind publication quotas.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

MAX_TECHNICAL_TREND_PER_PERIOD = 1
TECHNICAL_TREND_RANK_WINDOW = 20

TECHNICAL_SIGNALS = (
    r"\bagent harness\b", r"\bagent framework\b", r"\bmcp\b", r"\bmodel context protocol\b",
    r"\bcontext engineering\b", r"\bcontext management\b", r"\btool use\b", r"\btool calling\b",
    r"\bcomputer use\b", r"\bagentic architecture\b", r"\borchestration\b", r"\bworkflow engine\b",
    r"\binference serving\b", r"\bllm serving\b", r"\binference stack\b", r"\bkv cache\b",
    r"\bspeculative decoding\b", r"\bpaged attention\b", r"\bcontinuous batching\b", r"\bdisaggregated inference\b",
    r"\bmoe\b", r"\bmixture of experts\b", r"\bquantization\b", r"\bdistillation\b", r"\bpruning\b",
    r"\bmodel compression\b", r"\bsmall language model\b", r"\bslm\b", r"\bmultimodal architecture\b",
    r"\btransformer architecture\b", r"\battention mechanism\b", r"\blong context\b", r"\bstate space model\b",
    r"\btraining infrastructure\b", r"\bai infrastructure\b", r"\bai infra\b", r"\bgpu cluster\b",
    r"\bgpu interconnect\b", r"\bnvlink\b", r"\btpu\b", r"\bnpu\b", r"\baccelerator architecture\b",
    r"\bdata center\b", r"\bdatacenter\b", r"\bserving efficiency\b", r"\bmemory optimization\b",
    r"\bvector database\b", r"\bretrieval architecture\b", r"\brag architecture\b", r"\bknowledge graph\b",
    r"\bevaluation harness\b", r"\bbenchmark architecture\b", r"\bobservability\b", r"\btracing\b",
    r"\bai security architecture\b", r"\bprompt injection\b", r"\btool sandbox\b", r"\bmodel gateway\b",
    r"\bprotocol\b", r"\bspecification\b", r"\bruntime\b", r"\bsdk\b", r"\bapi architecture\b",
    r"هارنس عامل", r"معماری عامل", r"پروتکل", r"زیرساخت هوش مصنوعی", r"استنتاج", r"کش کی‌وی",
)

TECHNICAL_SOURCE_TYPES = {
    "research", "scientific", "technical_report", "technical", "official", "documentation", "specification", "standard",
}
EXCLUDED_SOURCE_MARKERS = ("reddit", "community", "aggregator", "arxiv.org", "arxiv")
AI_ANCHORS = (
    "artificial intelligence", "ai", "machine learning", "llm", "large language model", "foundation model",
    "agent", "agentic", "openai", "anthropic", "deepmind", "nvidia", "transformer", "هوش مصنوعی", "یادگیری ماشین",
)


def _text(item: dict[str, Any]) -> str:
    fields = ("title", "summary", "description", "category", "mission_area", "content_type", "tags", "keywords", "source")
    return " ".join(str(item.get(key) or "") for key in fields).casefold()


def _source_text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key) or "") for key in ("source", "source_name", "source_type", "source_domain", "publisher")).casefold()


def _technical_signal_count(text: str) -> int:
    return sum(1 for pattern in TECHNICAL_SIGNALS if re.search(pattern, text))


def _ai_related(text: str) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(anchor)}(?![a-z])", text) for anchor in AI_ANCHORS)


def _source_authority(item: dict[str, Any]) -> float:
    try:
        tier = int(item.get("source_tier", item.get("tier", 3)) or 3)
    except (TypeError, ValueError):
        tier = 3
    tier_score = {1: 18.0, 2: 12.0, 3: 4.0}.get(tier, 0.0)
    source_type = str(item.get("source_type") or "").strip().casefold()
    type_score = 10.0 if source_type in TECHNICAL_SOURCE_TYPES else 0.0
    if bool(item.get("official")):
        type_score += 5.0
    return min(30.0, tier_score + type_score)


def _recency_bonus(item: dict[str, Any]) -> float:
    raw = str(item.get("published") or item.get("published_at") or item.get("date") or "").strip()
    if not raw:
        return 0.0
    value = raw.replace("Z", "+00:00")
