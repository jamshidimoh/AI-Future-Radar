"""High-priority detection for major AI model releases."""
from __future__ import annotations

import re

MAJOR_AI_LABS = {
    "openai", "anthropic", "google", "google deepmind", "deepmind", "meta", "xai",
    "mistral", "deepseek", "alibaba", "alibaba cloud", "qwen", "z.ai", "moonshot",
    "nvidia", "microsoft ai", "microsoft", "amazon", "aws",
}
MODEL_TERMS = {
    "new model", "new ai model", "model release", "model releases", "released a model",
    "launches model", "launched model", "unveils model", "unveiled model", "introduces model",
    "introduced model", "foundation model", "frontier model", "open-weight model", "open weights",
    "reasoning model", "multimodal model", "language model", "large language model",
    "model update", "model upgrade", "weights release", "weights released",
}
RELEASE_TERMS = {
    "launch", "launched", "release", "released", "unveil", "unveiled", "introduce",
    "introduced", "announced", "available", "now available", "preview", "debut", "ships",
    "shipping", "open sourced", "open-source", "open source", "weights released",
}
MODEL_FAMILIES = (
    "gpt", "claude", "gemini", "gemma", "llama", "grok", "qwen", "deepseek", "kimi",
    "mistral", "mixtral", "ministral", "glm", "nemotron", "muse", "nova", "command",
    "phi", "jamba", "sonnet", "opus", "haiku",
)


def _text(item):
    return " ".join(str(item.get(k) or "") for k in ("title", "summary", "description", "source", "model_name")).lower()


def _has_model_identifier(text):
    """Detect versioned model identifiers with bounded, linear work.

    The previous implementation used nested variable-length regexes that could
    backtrack for minutes on long descriptions. This implementation tokenizes once
    and checks only a bounded four-token window around each model family. Compact
    names such as Qwen3.8 and GPT-OSS-120B are normalized before scanning.
    """
    normalized = re.sub(r"[^a-z0-9._-]+", " ", text.lower())
    normalized = re.sub(r"[-_]+", "-", normalized)

    # Split compact identifiers like qwen3.8 into [qwen, 3.8], while keeping
    # hyphenated variants such as gpt-oss-120b as a bounded sequence.
    tokens = []
    for raw in normalized.split():
        parts = [part for part in raw.split("-") if part]
        for part in parts:
            match = re.fullmatch(r"([a-z]+)(\d+(?:\.\d+)*)", part)
            if match:
                tokens.extend([match.group(1), match.group(2)])
            else:
                tokens.append(part)

    families = set(MODEL_FAMILIES)
    for index, token in enumerate(tokens):
        if token not in families:
            continue
        window = tokens[index + 1:index + 5]
        if any(any(char.isdigit() for char in candidate) for candidate in window):
            return True
    return False


def _has_explicit_model_language(text):
    return any(term in text for term in MODEL_TERMS)


def is_major_model_release(item):
    """Detect a substantive major model launch/update, not generic company news."""
    text = _text(item)
    lab = any(name in text for name in MAJOR_AI_LABS)
    release = any(term in text for term in RELEASE_TERMS)
    explicit = _has_explicit_model_language(text)
    named_model = _has_model_identifier(text)
    content_type = str(item.get("content_type") or "").lower()
    model_signal = explicit or named_model
    if not model_signal or not release or not lab:
        return False
    if content_type not in {"product_news", "official", "news", "research"}:
        return False
    return True


def model_release_bonus(item):
    return 32.0 if is_major_model_release(item) else 0.0
