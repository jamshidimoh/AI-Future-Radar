"""Deterministic cross-domain convergence analysis for Radar trends.

G5 identifies convergence only when independently observed domains share
claims/signals or explicit conceptual anchors. The layer is publication-
decoupled and intended for later foresight consumption.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
DEFAULT_CONFIG: dict[str, Any] = {
    "minimum_domains": 2,
    "minimum_shared_claims": 1,
    "minimum_independent_sources": 2,
    "convergence_threshold": 0.50,
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9_./+#:-]+|[\u0600-\u06FF]+")
_STOP = {"the", "and", "for", "with", "from", "this", "that", "about", "into", "این", "آن", "برای", "با", "در", "از", "به", "که", "و", "یک"}


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: object) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(value or "")) if len(token) >= 3 and token.lower() not in _STOP}


def validate_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(dict(config or {}))
    cfg["minimum_domains"] = int(cfg["minimum_domains"])
    cfg["minimum_shared_claims"] = int(cfg["minimum_shared_claims"])
    cfg["minimum_independent_sources"] = int(cfg["minimum_independent_sources"])
    cfg["convergence_threshold"] = float(cfg["convergence_threshold"])
    if cfg["minimum_domains"] < 2:
        raise ValueError("minimum_domains must be >= 2")
    if cfg["minimum_shared_claims"] < 1:
        raise ValueError("minimum_shared_claims must be >= 1")
    if cfg["minimum_independent_sources"] < 2:
        raise ValueError("minimum_independent_sources must be >= 2")
    if not 0.0 <= cfg["convergence_threshold"] <= 1.0:
        raise ValueError("convergence_threshold must be in [0, 1]")
    return cfg


def _stable_id(domains: Sequence[str], anchors: Sequence[str]) -> str:
    payload = {"domains": sorted(_norm(x) for x in domains), "anchors": sorted(_norm(x) for x in anchors)}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"conv-g5-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:20]}"


def _extract_claims(trend: Mapping[str, Any]) -> set[str]:
    claims = trend.get("claim_ids") or trend.get("claims") or []
    if isinstance(claims, str):
        claims = [claims]
    return {str(x) for x in claims if str(x)}


def _extract_sources(trend: Mapping[str, Any]) -> set[str]:
    sources = trend.get("source_ids") or trend.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    return {str(x) for x in sources if str(x)}


def _extract_domains(trend: Mapping[str, Any]) -> set[str]:
    domains = trend.get("domains") or trend.get("domain") or trend.get("categories") or []
    if isinstance(domains, str):
        domains = [domains]
    return {_norm(x) for x in domains if _norm(x)}


def _anchor_tokens(trend: Mapping[str, Any]) -> set[str]:
    return _tokens(" ".join(str(trend.get(key) or "") for key in ("label", "title", "summary", "why_it_matters")))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def analyze_convergence_pair(left: Mapping[str, Any], right: Mapping[str, Any], config: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    cfg = validate_config(config)
    left_id = str(left.get("trend_id") or left.get("cluster_id") or "")
    right_id = str(right.get("trend_id") or right.get("cluster_id") or "")
    if not left_id or not right_id or left_id == right_id:
        return None
    left_domains = _extract_domains(left)
    right_domains = _extract_domains(right)
    domains = sorted(left_domains | right_domains)
    if len(domains) < cfg["minimum_domains"]:
        return None
    shared_claims = sorted(_extract_claims(left) & _extract_claims(right))
    shared_tokens = sorted(_anchor_tokens(left) & _anchor_tokens(right))
    independent_sources = _extract_sources(left) | _extract_sources(right)
    if len(shared_claims) < cfg["minimum_shared_claims"] and not shared_tokens:
        return None
    if len(independent_sources) < cfg["minimum_independent_sources"]:
        return None

    claim_component = min(1.0, len(shared_claims) / max(1, min(len(_extract_claims(left)) or 1, len(_extract_claims(right)) or 1)))
    token_component = _jaccard(_anchor_tokens(left), _anchor_tokens(right))
    domain_component = min(1.0, len(domains) / max(cfg["minimum_domains"], 2))
    independence_component = min(1.0, len(independent_sources) / max(cfg["minimum_independent_sources"], 2))
    score = 0.45 * claim_component + 0.25 * token_component + 0.15 * domain_component + 0.15 * independence_component
    if score < cfg["convergence_threshold"]:
        return None
    return {
        "schema_version": SCHEMA_VERSION,
        "convergence_id": _stable_id(domains, [*shared_claims, *shared_tokens]),
        "trend_ids": sorted([left_id, right_id]),
        "domains": domains,
        "shared_claim_ids": shared_claims,
        "shared_anchor_tokens": shared_tokens,
        "independent_source_count": len(independent_sources),
        "claim_component": round(claim_component, 3),
        "anchor_component": round(token_component, 3),
        "domain_component": round(domain_component, 3),
        "independence_component": round(independence_component, 3),
        "convergence_score": round(score, 3),
        "convergence_class": "strong" if score >= 0.75 else "moderate",
    }


def analyze_convergence(trends: Iterable[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = validate_config(config)
    rows = [dict(trend) for trend in trends]
    rows.sort(key=lambda row: str(row.get("trend_id") or row.get("cluster_id") or ""))
    output: list[dict[str, Any]] = []
    by_domain: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for trend in rows:
        for domain in _extract_domains(trend):
            by_domain[domain].append(trend)
    domain_names = sorted(by_domain)
    for i, left_domain in enumerate(domain_names):
        for right_domain in domain_names[i + 1 :]:
            for left in by_domain[left_domain]:
                for right in by_domain[right_domain]:
                    result = analyze_convergence_pair(left, right, cfg)
                    if result and result not in output:
                        output.append(result)
    output.sort(key=lambda row: (-row["convergence_score"], row["convergence_id"]))
    return json.loads(json.dumps(output, ensure_ascii=False, sort_keys=True))


def validate_convergence(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        if int(record.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported convergence schema_version")
        cid = str(record.get("convergence_id") or "")
        trend_ids = record.get("trend_ids")
        domains = record.get("domains")
        score = float(record.get("convergence_score", -1))
        if not cid or cid in seen or not isinstance(trend_ids, list) or len(trend_ids) < 2:
            raise ValueError("invalid convergence identity")
        if not isinstance(domains, list) or len(set(domains)) < 2:
            raise ValueError("convergence requires at least two domains")
        if not 0.0 <= score <= 1.0:
            raise ValueError("convergence_score must be in [0, 1]")
        seen.add(cid)
        result.append(dict(record))
    return result
