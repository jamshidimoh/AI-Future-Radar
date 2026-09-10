"""Dynamic, failover-oriented source selection for Education.

The selector is intentionally local and deterministic: it does not trust a
single hard-coded URL. It builds a small topic-aware candidate pool from
curated authoritative sources, ranks by relevance/authority, and leaves
reachability, freshness, and independence to the existing source gates.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse


# Curated, durable source pool. Availability is checked at runtime by the
# existing _fetch_reference + education_source_policy gates.
SOURCE_POOL = [
    {"name": "NIST AI Resource Center", "url": "https://airc.nist.gov/", "keywords": ["ai", "artificial intelligence", "agent", "safety", "evaluation", "standard"], "authority": 100},
    {"name": "NIST AI Glossary", "url": "https://csrc.nist.gov/glossary", "keywords": ["ai", "artificial intelligence", "machine learning", "model", "learning"], "authority": 98},
    {"name": "Stanford AI Index 2026", "url": "https://hai.stanford.edu/ai-index/2026-ai-index-report", "keywords": ["ai", "artificial intelligence", "model", "agent", "benchmark", "trend"], "authority": 96},
    {"name": "Google AI Developers", "url": "https://ai.google.dev/", "keywords": ["ai", "agent", "gemini", "llm", "multimodal", "model"], "authority": 94},
    {"name": "Google Cloud AI", "url": "https://cloud.google.com/ai", "keywords": ["ai", "agent", "llm", "machine learning", "enterprise"], "authority": 92},
    {"name": "Microsoft Learn AI", "url": "https://learn.microsoft.com/en-us/ai/", "keywords": ["ai", "agent", "copilot", "memory", "machine learning", "llm"], "authority": 94},
    {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/", "keywords": ["ai", "agent", "memory", "research", "model", "learning"], "authority": 96},
    {"name": "IBM Think AI", "url": "https://www.ibm.com/think/topics/artificial-intelligence", "keywords": ["ai", "agent", "enterprise", "model", "machine learning"], "authority": 90},
    {"name": "IBM watsonx Docs", "url": "https://www.ibm.com/docs/en/watsonx", "keywords": ["ai", "agent", "memory", "orchestration", "model"], "authority": 91},
    {"name": "Hugging Face Documentation", "url": "https://huggingface.co/docs", "keywords": ["llm", "transformer", "model", "embedding", "agent", "machine learning"], "authority": 88},
    {"name": "scikit-learn Documentation", "url": "https://scikit-learn.org/stable/user_guide.html", "keywords": ["machine learning", "classification", "regression", "clustering", "model", "evaluation"], "authority": 88},
    {"name": "OpenAI Platform Documentation", "url": "https://platform.openai.com/docs/", "keywords": ["ai", "agent", "llm", "model", "tool", "structured output"], "authority": 93},
    {"name": "Anthropic Engineering", "url": "https://www.anthropic.com/engineering", "keywords": ["ai", "agent", "evaluation", "llm", "memory", "safety"], "authority": 93},
    {"name": "NVIDIA AI Documentation", "url": "https://docs.nvidia.com/ai/", "keywords": ["ai", "model", "inference", "gpu", "agent", "machine learning"], "authority": 90},
]


def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", str(text or "").lower())}


def _lesson_text(lesson: dict) -> str:
    parts = [lesson.get("title"), lesson.get("domain"), lesson.get("relation"), lesson.get("prerequisites")]
    for key in ("a", "b"):
        term = lesson.get(key) or {}
        parts.extend([term.get("term"), term.get("fa"), term.get("seed")])
    return " ".join(str(x) for x in parts if x is not None)


def _topic_score(lesson: dict, source: dict) -> int:
    text = _lesson_text(lesson).lower()
    tokens = _tokens(text)
    score = 0
    for keyword in source.get("keywords", []):
        key = str(keyword).lower()
        if " " in key:
            if key in text:
                score += 8
        elif key in tokens:
            score += 5
    return score


def _same_url(a: str, b: str) -> bool:
    return str(a or "").rstrip("/").lower() == str(b or "").rstrip("/").lower()


def dynamic_source_candidates(lesson: dict, existing: list[dict] | None = None, *, limit: int = 8) -> list[dict]:
    """Return existing sources plus topic-ranked dynamic fallbacks.

    Existing lesson-specific sources remain first-class candidates. Dynamic
    sources are only an additional pool, so a curriculum author can still
    pin a preferred source. The runtime gate decides which candidates survive.
    """
    existing = list(existing or [])
    seen = {str(x.get("url", "")).rstrip("/").lower() for x in existing if x.get("url")}
    scored = []
    for source in SOURCE_POOL:
        if _same_url(source.get("url"), "") or str(source.get("url")).rstrip("/").lower() in seen:
            continue
        score = _topic_score(lesson, source)
        if score <= 0:
            continue
        item = dict(source)
        item["dynamic_relevance"] = score
        scored.append(item)
    scored.sort(key=lambda x: (int(x.get("dynamic_relevance", 0)), int(x.get("authority", 0)), str(x.get("url", ""))), reverse=True)
    return existing + scored[: max(0, int(limit))]


def rank_verified_sources(sources: list[dict]) -> list[dict]:
    """Prefer relevance/authority while retaining organization diversity."""
    return sorted(
        [dict(x) for x in sources],
        key=lambda x: (
            int(x.get("dynamic_relevance", 0)),
            int(x.get("authority_score", x.get("authority", 0))),
            -int(x.get("authority_tier", 4)),
            str(x.get("url", "")),
        ),
        reverse=True,
    )
