"""Claim-to-source pre-check and shadow semantic verifier.

The first version is deliberately non-blocking. Deterministic checks flag
risk-bearing claims, while the optional semantic verifier records an
interpretation without changing publication eligibility.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from src.llm_router_light import call_llm_with_fallback, get_quality_chain

SCHEMA_VERSION = "claim-verification.v1"

REASON_CODES = {
    "numeric_mismatch",
    "numeric_unit_mismatch",
    "date_mismatch",
    "unsupported_named_entity",
    "unsupported_model_version",
    "unsupported_benchmark",
    "unsupported_comparison",
    "unsupported_superlative",
    "causal_overreach",
    "unsupported_attribution",
    "unsupported_quote",
    "temporal_mismatch",
    "insufficient_source_evidence",
    "semantic_entailment_failure",
    "verifier_provider_failure",
    "verifier_timeout",
}

RISK_TYPES = (
    "numeric_claim",
    "named_entity_claim",
    "benchmark_claim",
    "model_version_claim",
    "comparison_claim",
    "superlative_claim",
    "causal_claim",
    "attribution_claim",
    "quote_claim",
    "date_claim",
)

_COMPARISON_RE = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?\s*%\s*(?:سریع|کند|بهتر|بیشتر|کمتر)|"
    r"(?:\b\d+(?:[.,]\d+)?\s*(?:x|×)\b)|"
    r"\b(?:faster|slower|better|worse|higher|lower|improved|improves|"
    r"outperforms|more accurate|less accurate|twice as)\b|"
    r"\b(?:than|versus|vs\.?|compared with|compared to)\b|"
    r"(?:سریع‌تر|کندتر|بهتر|بدتر|بیشتر|کمتر|برتر|دو برابر|در مقایسه با|نسبت به))",
    re.IGNORECASE,
)
_SUPERLATIVE_RE = re.compile(
    r"(?:\b(?:first|only|largest|smallest|best|worst|most|least|leading|state[- ]of[- ]the[- ]art)\b|"
    r"(?:اولین|تنها|بزرگ‌ترین|کوچک‌ترین|بهترین|بدترین|برترین|پیشرفته‌ترین))",
    re.IGNORECASE,
)
_CAUSAL_RE = re.compile(
    r"(?:باعث(?:\s+شد)?|منجر\s+شد|سبب(?:\s+شد)?|به\s+دلیل|در\s+نتیجه|زیرا|چون|موجب(?:\s+شد)?|"
    r"\bleads? to\b|\bcauses?\b|\bresults? in\b|\bbecause\b|\btherefore\b|\bdrives?\b)",
    re.IGNORECASE,
)
_ATTRIBUTION_RE = re.compile(
    r"(?:به\s+گفته(?:ی|ِ)?|طبق\s+گفته|بر\s+اساس\s+گزارش|از\s+دیدگاه|\baccording to\b|\bsaid\b|\breported by\b|\baccording\s+to\b)",
    re.IGNORECASE,
)
_QUOTE_RE = re.compile(r'["“”«»]([^"“”«»\n]{2,240})["“”«»]')
_NUMBER_RE = re.compile(r"(?<![\w])(?:\d{1,3}(?:[,_]\d{3})+|\d+(?:[.,]\d+)?)\s*(?:%|٪|percent|درصد|x|×|[KMB](?:B)?|هزار|میلیون|میلیارد)?", re.IGNORECASE)
_DATE_RE = re.compile(r"(?<!\d)(?:\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})(?!\d)")
_BENCHMARK_RE = re.compile(r"\b(?:SWE-bench|MMLU(?:-Pro)?|GPQA(?:-Diamond)?|HumanEval|AIME(?:\s*\d{4})?|GSM8K|BIG-bench|ARC[- ]?AGI|MMMU|LiveBench|HELM|TruthfulQA|IFEval)\b", re.IGNORECASE)
_MODEL_RE = re.compile(r"\b(?:GPT[- ]?\d+(?:\.\d+)*|Claude(?:[- ]?(?:2|3|4)(?:\.\d+)*)?|Gemini(?:[- ]?\d+(?:\.\d+)*)?|Llama(?:[- ]?\d+(?:\.\d+)*)?|Qwen(?:[- ]?\d+(?:\.\d+)*)?|Grok(?:[- ]?\d+(?:\.\d+)*)?)\b", re.IGNORECASE)
_ENTITY_RE = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:[ ._-][A-Z][A-Za-z0-9]+){0,3}\b")

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


@dataclass(frozen=True)
class RiskFlags:
    numeric_claim: bool = False
    named_entity_claim: bool = False
    benchmark_claim: bool = False
    model_version_claim: bool = False
    comparison_claim: bool = False
    superlative_claim: bool = False
    causal_claim: bool = False
    attribution_claim: bool = False
    quote_claim: bool = False
    date_claim: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {name: bool(getattr(self, name)) for name in RISK_TYPES}


@dataclass(frozen=True)
class Claim:
    id: str
    type: str
    text: str
    risk: str = "medium"

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "type": self.type, "text": self.text, "risk": self.risk}


@dataclass
class VerificationResult:
    status: str
    overall_confidence: float | None
    claims: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    provider: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "overall_confidence": self.overall_confidence,
            "claim_count": len(self.claims),
            "claims": self.claims,
            "flags": self.flags,
            "provider": self.provider,
        }


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).translate(_PERSIAN_DIGITS)
    value = value.replace("٪", "%").replace("×", "x")
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value


def _contains(source_norm: str, value: str) -> bool:
    return normalize_text(value) in source_norm


def _numbers(text: str) -> list[str]:
    return [normalize_text(x) for x in _NUMBER_RE.findall(text)]


def _make_flags(title: str, summary: str, why: str, source: str) -> tuple[RiskFlags, list[Claim], list[str]]:
    output = " ".join((title or "", summary or "", why or "")).strip()
    source_norm = normalize_text(source)
    flags = {
        name: False for name in RISK_TYPES
    }
    claims: list[Claim] = []
    unsupported: list[str] = []

    nums = _numbers(output)
    if nums:
        flags["numeric_claim"] = True
        for i, number in enumerate(nums, 1):
            support = _contains(source_norm, number.replace(",", "")) or _contains(source_norm, number)
            claims.append(Claim(f"n{i}", "numeric", number, "high"))
            if not support:
                unsupported.append("numeric_mismatch")

    dates = _DATE_RE.findall(output)
    if dates:
        flags["date_claim"] = True
        for i, date in enumerate(dates, 1):
            claims.append(Claim(f"d{i}", "date", date, "high"))
            if not _contains(source_norm, date):
                unsupported.append("date_mismatch")

    models = _MODEL_RE.findall(output)
    if models:
        flags["model_version_claim"] = True
        for i, model in enumerate(models, 1):
            claims.append(Claim(f"m{i}", "model_version", model, "high"))
            if not _contains(source_norm, model):
                unsupported.append("unsupported_model_version")

    benchmarks = _BENCHMARK_RE.findall(output)
    if benchmarks:
        flags["benchmark_claim"] = True
        for i, benchmark in enumerate(benchmarks, 1):
            claims.append(Claim(f"b{i}", "benchmark", benchmark, "high"))
            if not _contains(source_norm, benchmark):
                unsupported.append("unsupported_benchmark")

    entities = []
    seen = set()
    for value in _ENTITY_RE.findall(output):
        key = normalize_text(value)
        if key in seen or key in {"Ai", "The", "This", "OpenAI"}:
            continue
        seen.add(key)
        if len(value) >= 4:
            entities.append(value)
    if entities:
        flags["named_entity_claim"] = True
        for i, entity in enumerate(entities, 1):
            claims.append(Claim(f"e{i}", "named_entity", entity, "high"))
            if not _contains(source_norm, entity):
                unsupported.append("unsupported_named_entity")

    if _COMPARISON_RE.search(output):
        flags["comparison_claim"] = True
        claims.append(Claim("c1", "comparison", _COMPARISON_RE.search(output).group(0), "high"))
    if _SUPERLATIVE_RE.search(output):
        flags["superlative_claim"] = True
        claims.append(Claim("s1", "superlative", _SUPERLATIVE_RE.search(output).group(0), "high"))
    if _CAUSAL_RE.search(output):
        flags["causal_claim"] = True
        claims.append(Claim("ca1", "causal", _CAUSAL_RE.search(output).group(0), "high"))
    if _ATTRIBUTION_RE.search(output):
        flags["attribution_claim"] = True
        claims.append(Claim("a1", "attribution", _ATTRIBUTION_RE.search(output).group(0), "high"))
    if _QUOTE_RE.search(output):
        flags["quote_claim"] = True
        claims.append(Claim("q1", "quote", _QUOTE_RE.search(output).group(1), "high"))
        if _QUOTE_RE.search(output).group(1) not in source:
            unsupported.append("unsupported_quote")

    if flags["comparison_claim"] and not _contains(source_norm, _COMPARISON_RE.search(normalize_text(source)).group(0) if _COMPARISON_RE.search(normalize_text(source)) else "__missing__"):
        unsupported.append("unsupported_comparison")
    if flags["superlative_claim"] and not _SUPERLATIVE_RE.search(source):
        unsupported.append("unsupported_superlative")
    if flags["causal_claim"] and not _CAUSAL_RE.search(source):
        unsupported.append("causal_overreach")
    if flags["attribution_claim"] and not _ATTRIBUTION_RE.search(source):
        unsupported.append("unsupported_attribution")

    unique = []
    for code in unsupported:
        if code not in unique:
            unique.append(code)
    return RiskFlags(**flags), claims, unique


def deterministic_precheck(title: str, summary: str, why_it_matters: str, source_text: str) -> dict[str, Any]:
    flags, claims, unsupported = _make_flags(title, summary, why_it_matters, source_text)
    return {
        "schema_version": SCHEMA_VERSION,
        "risk_flags": flags.as_dict(),
        "claims": [claim.as_dict() for claim in claims],
        "flags": unsupported,
        "requires_semantic_verification": bool(claims),
    }


_DEFAULT_VERIFIER_PROMPT = """You are a strict claim-to-source verifier for a technology news radar.
Do not rewrite the summary. Determine only whether each listed claim is supported by the supplied source text.
Use only the source text; do not rely on outside knowledge.
Return JSON only:
{"status":"VERIFIED|NEEDS_REVIEW|REJECTED|UNAVAILABLE","overall_confidence":0.0,"claims":[{"id":"c1","support":"SUPPORTED|PARTIAL|UNSUPPORTED|NOT_APPLICABLE","confidence":0.0,"reason_code":null}],"flags":[]}
Reason codes may include: numeric_mismatch, numeric_unit_mismatch, date_mismatch, unsupported_named_entity, unsupported_model_version, unsupported_benchmark, unsupported_comparison, unsupported_superlative, causal_overreach, unsupported_attribution, unsupported_quote, temporal_mismatch, insufficient_source_evidence, semantic_entailment_failure.
"""


def _extract_json(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise TypeError("verifier response must be an object")
    return value


def semantic_verify(
    *,
    source_text: str,
    title: str,
    summary: str,
    why_it_matters: str,
    precheck: Mapping[str, Any],
    call_fn: Callable[..., tuple[str | None, str | None]] | None = None,
) -> VerificationResult:
    claims = list(precheck.get("claims") or [])
    if not claims:
        return VerificationResult("NOT_APPLICABLE", 1.0, [], list(precheck.get("flags") or []), None)
    caller = call_fn or call_llm_with_fallback
    user_payload = {
        "title": title,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "claims": claims,
        "source": source_text,
    }
    try:
        raw, provider = caller(
            _DEFAULT_VERIFIER_PROMPT,
            json.dumps(user_payload, ensure_ascii=False),
            providers=get_quality_chain(),
        )
    except TimeoutError:
        return VerificationResult("UNAVAILABLE", None, [], ["verifier_timeout"], None)
    except Exception:
        return VerificationResult("UNAVAILABLE", None, [], ["verifier_provider_failure"], None)
    if not raw:
        return VerificationResult("UNAVAILABLE", None, [], ["verifier_provider_failure"], provider)
    try:
        data = _extract_json(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return VerificationResult("UNAVAILABLE", None, [], ["verifier_provider_failure"], provider)

    result_claims = []
    flags = list(precheck.get("flags") or [])
    for claim in data.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        normalized = {
            "id": str(claim.get("id") or ""),
            "support": str(claim.get("support") or "NOT_APPLICABLE").upper(),
            "confidence": _safe_confidence(claim.get("confidence")),
            "reason_code": claim.get("reason_code") if claim.get("reason_code") in REASON_CODES else None,
        }
        result_claims.append(normalized)
        if normalized["reason_code"] and normalized["reason_code"] not in flags:
            flags.append(normalized["reason_code"])

    status = str(data.get("status") or "NEEDS_REVIEW").upper()
    if status not in {"VERIFIED", "NEEDS_REVIEW", "REJECTED", "UNAVAILABLE"}:
        status = "NEEDS_REVIEW"
    return VerificationResult(
        status,
        _safe_confidence(data.get("overall_confidence")),
        result_claims,
        flags,
        provider,
    )


def _safe_confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, number))
