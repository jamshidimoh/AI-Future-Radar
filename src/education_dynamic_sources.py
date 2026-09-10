"""Dynamic, fail-closed source selection for educational lessons.

The selector never replaces the existing source-policy gates. It only builds a
larger candidate pool and ranks candidates before the existing fetch/current/
independence validation performed by educational_content.py.
"""
from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse

# Broad, stable authority pools. Topic-specific lesson sources/fallbacks are
# still preferred; these are safety-net candidates when a configured URL dies.
DOMAIN_POOLS = {
    "ai": [
        {"name": "NIST AI Glossary", "url": "https://csrc.nist.gov/glossary/term/artificial_intelligence", "authority_score": 100},
        {"name": "Stanford AI Index 2026", "url": "https://hai.stanford.edu/ai-index/2026-ai-index-report", "authority_score": 98},
        {"name": "Google Research", "url": "https://research.google/", "authority_score": 94},
        {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/", "authority_score": 94},
    ],
    "agent": [
        {"name": "Anthropic Research", "url": "https://www.anthropic.com/research", "authority_score": 96},
        {"name": "OpenAI Research", "url": "https://openai.com/research/", "authority_score": 96},
        {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/", "authority_score": 94},
        {"name": "AWS Machine Learning Blog", "url": "https://aws.amazon.com/blogs/machine-learning/", "authority_score": 92},
        {"name": "IBM Think", "url": "https://www.ibm.com/think/topics/artificial-intelligence", "authority_score": 90},
    ],
    "memory": [
        {"name": "AWS AgentCore Memory Documentation", "url": "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-memory-metadata.html", "authority_score": 99},
        {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/", "authority_score": 94},
        {"name": "Microsoft Learn", "url": "https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge/memory", "authority_score": 94},
        {"name": "IBM Think — AI Agent Memory", "url": "https://www.ibm.com/think/topics/ai-agent-memory", "authority_score": 90},
        {"name": "IBM watsonx Orchestrate Documentation", "url": "https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=chat-understanding-agent-memory", "authority_score": 90},
    ],
    "quantum": [
        {"name": "NIST Quantum Information Science", "url": "https://www.nist.gov/quantum-information-science", "authority_score": 100},
        {"name": "IBM Quantum Learning", "url": "https://quantum.cloud.ibm.com/learning", "authority_score": 96},
    ],
}

KEYWORD_GROUPS = {
    "memory": ("memory", "memor", "context memory", "agentic memory", "structured memory", "episodic", "semantic memory", "procedural memory"),
    "agent": ("agent", "agentic", "tool use", "function calling", "multi-agent", "orchestration", "computer use"),
    "quantum": ("quantum", "qubit", "superposition", "entanglement", "quantum computing"),
}


def _text(lesson: dict) -> str:
    parts = [lesson.get("title"), lesson.get("domain"), lesson.get("description")]
    for key in ("a", "b"):
        value = lesson.get(key) or {}
        if isinstance(value, dict):
            parts.extend(value.get(k) for k in ("term", "fa", "seed"))
    parts.extend(lesson.get("keywords") or [])
    return " ".join(str(x or "") for x in parts).lower()


def _pool_keys(lesson: dict) -> list[str]:
    text = _text(lesson)
    keys = []
    for key, terms in KEYWORD_GROUPS.items():
        if any(term in text for term in terms):
            keys.append(key)
    if not keys:
        keys.append("ai")
    return keys


def build_candidate_pool(lesson: dict, configured: list[dict]) -> list[dict]:
    """Return a deterministic, deduplicated, topic-aware candidate pool."""
    candidates = [dict(x) for x in configured if isinstance(x, dict)]
    existing = {str(x.get("url", "")).strip() for x in candidates}
    for key in _pool_keys(lesson):
        for candidate in DOMAIN_POOLS.get(key, []):
            url = candidate["url"]
            if url in existing:
                continue
            candidates.append(dict(candidate))
            existing.add(url)

    # Prefer explicitly configured sources, then authority, then URL for
    # deterministic behavior. The fetch/current gates remain authoritative.
    def sort_key(item):
        explicit = 1 if item.get("url") in {str(x.get("url", "")).strip() for x in configured} else 0
        return (-explicit, -int(item.get("authority_score", 0) or 0), str(item.get("url", "")))

    return sorted(candidates, key=sort_key)


def independent_domains(sources: list[dict]) -> int:
    domains = {urlparse(str(x.get("url", ""))).netloc.lower().removeprefix("www.") for x in sources}
    return len({d for d in domains if d})
