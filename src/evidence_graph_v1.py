"""Deterministic evidence graph and claim provenance for Radar intelligence.

G3 is deliberately publication-decoupled.  The graph records source/claim
provenance and evidence relations without changing editorial ranking,
selection, quotas, or delivery.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA_VERSION = 1
_ALLOWED_NODE_TYPES = {"source", "claim", "trend"}
_ALLOWED_RELATIONS = {"supports", "contradicts", "derived_from", "observed_in"}
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_./+#:-]+|[\u0600-\u06FF]+")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def canonical_source_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        query = [
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in _TRACKING_PARAMS
        ]
        path = re.sub(r"/+", "/", parts.path or "/").rstrip("/") or "/"
        return urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), "")
        )
    except Exception:
        return raw.split("#", 1)[0].strip().rstrip("/")


def _stable_id(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:20]}"


def source_id(source: Mapping[str, Any]) -> str:
    canonical = canonical_source_url(source.get("canonical_url") or source.get("link") or source.get("url"))
    if canonical:
        return _stable_id("source-g3", canonical)
    title = _normalize_text(source.get("title"))
    if not title:
        raise ValueError("source requires a URL or title")
    return _stable_id("source-g3", {"title": title})


def claim_id(claim_text: object) -> str:
    normalized = _normalize_text(claim_text)
    if not normalized:
        raise ValueError("claim text must not be empty")
    return _stable_id("claim-g3", normalized)


def trend_id(trend: Mapping[str, Any]) -> str:
    explicit = str(trend.get("cluster_id") or trend.get("trend_id") or "").strip()
    if explicit:
        return explicit
    members = sorted(str(x) for x in trend.get("member_ids", []) if str(x))
    if not members:
        raise ValueError("trend requires cluster_id/trend_id or member_ids")
    return _stable_id("trend-g3", members)


def _node(node_id: str, node_type: str, **payload: Any) -> dict[str, Any]:
    if node_type not in _ALLOWED_NODE_TYPES:
        raise ValueError(f"unsupported node type: {node_type}")
    result = {"id": node_id, "type": node_type}
    result.update(payload)
    return result


def _edge(source: str, target: str, relation: str, confidence: float, **payload: Any) -> dict[str, Any]:
    if relation not in _ALLOWED_RELATIONS:
        raise ValueError(f"unsupported relation: {relation}")
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("edge confidence must be in [0, 1]")
    result = {
        "source": str(source),
        "target": str(target),
        "relation": relation,
        "confidence": round(float(confidence), 3),
    }
    result.update(payload)
    return result


def _claims_from_item(item: Mapping[str, Any]) -> list[tuple[str, str, float]]:
    claims = item.get("claims")
    if claims is None:
        fallback = item.get("claim")
        claims = [fallback] if fallback else []
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        raise ValueError("item.claims must be a sequence")
    output: list[tuple[str, str, float]] = []
    for value in claims:
        if isinstance(value, str):
            output.append((value, "supports", 1.0))
            continue
        if not isinstance(value, Mapping):
            raise ValueError("claim entries must be strings or mappings")
        text = str(value.get("text") or value.get("claim") or "").strip()
        relation = str(value.get("relation") or "supports")
        confidence = float(value.get("confidence", 1.0))
        if not text:
            raise ValueError("claim text must not be empty")
        output.append((text, relation, confidence))
    return output


def build_evidence_graph(
    sources: Iterable[Mapping[str, Any]],
    trends: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, serializable provenance graph.

    Each source contributes source->claim evidence edges.  A trend, when
    provided, receives derived_from edges from its claims.  Contradictory
    evidence is represented explicitly rather than discarded.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: set[str] = set()

    def add_node(node: dict[str, Any]) -> None:
        existing = nodes.get(node["id"])
        if existing is None:
            nodes[node["id"]] = node
            return
        if existing["type"] != node["type"]:
            raise ValueError(f"node id collision across types: {node['id']}")

    def add_edge(edge: dict[str, Any]) -> None:
        key = json.dumps(edge, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        edges.add(key)

    source_claims: dict[str, set[str]] = {}
    for raw in sources:
        source = dict(raw)
        sid = source_id(source)
        title = str(source.get("title") or "").strip()
        canonical = canonical_source_url(source.get("canonical_url") or source.get("link") or source.get("url"))
        add_node(_node(sid, "source", title=title, canonical_url=canonical, source_type=str(source.get("source_type") or "unknown")))
        for text, relation, confidence in _claims_from_item(source):
            cid = claim_id(text)
            add_node(_node(cid, "claim", text=_normalize_text(text)))
            add_edge(_edge(sid, cid, relation, confidence, provenance="source_claim"))
            source_claims.setdefault(sid, set()).add(cid)

    for raw_trend in trends or []:
        trend = dict(raw_trend)
        tid = trend_id(trend)
        add_node(_node(tid, "trend", label=str(trend.get("label") or trend.get("title") or tid), member_ids=sorted(str(x) for x in trend.get("member_ids", []))))
        claim_ids = [str(x) for x in trend.get("claim_ids", []) if str(x)]
        for cid in sorted(set(claim_ids)):
            if cid not in nodes or nodes[cid]["type"] != "claim":
                raise ValueError(f"trend references unknown claim node: {cid}")
            add_edge(_edge(cid, tid, "derived_from", float(trend.get("confidence", 1.0) or 0.0), provenance="claim_trend"))

    edge_records = [json.loads(value) for value in sorted(edges)]
    node_records = [nodes[key] for key in sorted(nodes)]
    return validate_graph({"schema_version": SCHEMA_VERSION, "nodes": node_records, "edges": edge_records})


def validate_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    if int(graph.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(f"unsupported graph schema_version: {graph.get('schema_version')}")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("graph.nodes and graph.edges must be lists")
    node_ids = set()
    node_types = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ValueError("graph node must be a mapping")
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if not node_id or node_type not in _ALLOWED_NODE_TYPES or node_id in node_ids:
            raise ValueError("invalid or duplicate graph node")
        node_ids.add(node_id)
        node_types[node_id] = node_type
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise ValueError("graph edge must be a mapping")
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        relation = str(edge.get("relation") or "")
        if source not in node_ids or target not in node_ids:
            raise ValueError("edge references an unknown node")
        if relation not in _ALLOWED_RELATIONS:
            raise ValueError("invalid edge relation")
        confidence = float(edge.get("confidence", -1))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("edge confidence must be in [0, 1]")
        if relation in {"supports", "contradicts"} and node_types[source] != "source":
            raise ValueError("supports/contradicts edges must originate at a source")
        if relation == "derived_from" and node_types[target] != "trend":
            raise ValueError("derived_from edges must target a trend")
        if relation == "observed_in" and node_types[target] != "source":
            raise ValueError("observed_in edges must target a source")
    return json.loads(json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def graph_snapshot(graph: Mapping[str, Any]) -> dict[str, Any]:
    return validate_graph(graph)
