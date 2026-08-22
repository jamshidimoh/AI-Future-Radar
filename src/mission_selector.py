"""Mission-driven portfolio selection for AI Future Radar."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from pioneer_radar.epistemic_tensions import tension_for_person
from pioneer_radar.pioneer_scoring import attach_pioneer_signal
from pioneer_radar.portfolio_safeguard import analytical_anchor
from pioneer_radar.source_priority import enrich_source_priority

ROOT = Path(__file__).resolve().parents[1]
PIONEERS_PATH = ROOT / "config" / "pioneers.yaml"

AREAS = {
    "ai_core": ["artificial intelligence", "llm", "foundation model", "reasoning", "agent", "agentic", "multimodal", "generative ai", "ai safety", "agi", "model", "machine learning"],
    "convergence": ["quantum", "quantum computing", "robotics", "humanoid", "brain-computer", "bci", "neurotechnology", "biotech", "synthetic biology", "genomics", "crispr", "protein", "materials", "semiconductor", "energy", "space", "neuromorphic", "organoid"],
    "mind_cognition": ["consciousness", "sentience", "cognitive science", "cognition", "mind", "brain", "neuroscience", "philosophy of mind", "philosophy of science", "machine consciousness", "awareness", "predictive processing", "active inference"],
    "future_governance": ["future of ai", "foresight", "governance", "policy", "jobs", "economy", "geopolitics", "existential risk", "alignment", "regulation", "future of work", "society", "civilization"],
}
FRONTIER = ["breakthrough", "new capability", "state of the art", "frontier", "first", "new model", "new architecture", "autonomous", "scaling", "reasoning", "agentic", "world model", "scientific discovery", "clinical", "deployment", "commercialized", "mechanistic interpretability", "interpretability"]
TREND = ["roadmap", "benchmark", "adoption", "infrastructure", "investment", "standard", "platform", "ecosystem", "policy", "regulation", "research direction", "trend", "forecast"]
LOW_SIGNAL = ["top 10", "best tools", "prompt collection", "weekly roundup", "productivity tips", "how to use chatgpt", "10 tools", "20 tools", "tool roundup"]
INTERVIEW_TYPES = {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a"}


def _load_pioneers() -> list[dict]:
    try:
        import yaml
        data = yaml.safe_load(PIONEERS_PATH.read_text(encoding="utf-8")) or {}
        return list(data.get("people") or [])
    except Exception:
        return []


def _text(item: dict) -> str:
    return " ".join(str(item.get(k) or "") for k in ("title", "summary", "description", "why_it_matters")).lower()


def _hits(text: str, terms: list[str]) -> int:
    return sum(1 for t in terms if str(t).lower() in text)


def _match_pioneer(item: dict) -> dict | None:
    text = _text(item)
    explicit = str(item.get("leader") or item.get("watch_person") or item.get("pioneer_name") or "").strip().casefold()
    for profile in _load_pioneers():
        name = str(profile.get("name") or "").strip()
        if not name:
            continue
        if explicit == name.casefold() or name.casefold() in text:
            return profile
    return None


def classify_area(item: dict) -> str:
    text = _text(item)
    scores = {area: _hits(text, terms) for area, terms in AREAS.items()}
    explicit = str(item.get("category") or "").lower().strip()
    mapping = {"quantum": "convergence", "genetics": "convergence", "mind": "mind_cognition", "future": "future_governance"}
    if explicit in mapping:
        scores[mapping[explicit]] += 3
    if explicit == "ai":
        scores["ai_core"] += 1
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "ai_core"


def _source_tier(item: dict) -> int:
    """Return an authority tier; explicit low-authority publishers override upstream optimistic metadata."""
    raw = item.get("source_tier")
    try:
        raw_tier = int(raw) if raw is not None else None
    except Exception:
        raw_tier = None
    hay = " ".join(str(item.get(k) or "").lower() for k in ("source", "source_url", "source_domain", "link"))
    low_authority = [
        "bitcoin world", "finance.biggo", "biggo.com", "tradingkey", "yellow.com", "yellow",
        "moomoo", "pulse 2.0", "mshale", "analyticsindiamag", "fortune india", "moneycontrol",
        "edtech innovation hub",
    ]
    if any(x in hay for x in low_authority):
        return 3
    tier1 = [
        "mit csail", "stanford hai", "bair", "deepmind", "openai", "anthropic", "google deepmind",
        "mit news", "nvidia newsroom", "microsoft research", "google research", "meta ai", "ibm research",
        "nature", "quanta", "nist", "ieee", "arxiv", "cmu", "sussex", "harvard", "princeton",
        "stanford", "berkeley", "caltech", "mit.edu", "edu",
    ]
    tier2 = [
        "mit technology review", "ieee spectrum", "ars technica", "reuters", "associated press", "ap news",
        "wired", "scientific american", "new scientist", "techcrunch", "the verge", "washington post",
        "new york times", "bbc", "financial times", "bloomberg", "the guardian", "nature news",
        "forbes", "cnbc", "fortune", "business insider", "36kr",
    ]
    if any(x in hay for x in tier1):
        return 1
    if any(x in hay for x in tier2):
        return 2
    if "reddit" in hay or "community" in hay or "aggregator" in hay:
        return 3
    return raw_tier if raw_tier in {1, 2, 3} else 3


def _is_interview(item: dict) -> bool:
    ctype = str(item.get("content_type") or "").lower()
    text = _text(item)
    return ctype in INTERVIEW_TYPES or bool(item.get("interview_signal")) or any(x in text for x in ["interview", "conversation", "podcast", "fireside", "keynote"])


def _leader_key(item: dict) -> str:
    for key in ("leader_name", "named_guest", "person_name", "guest_name", "leader", "watch_person", "pioneer_name"):
        value = str(item.get(key) or "").strip().casefold()
        if value:
            return value
    return str(item.get("canonical_url") or item.get("url") or item.get("link") or item.get("title") or "").strip().casefold()


def _is_protected_leader(item: dict) -> bool:
    slot = str(item.get("editorial_slot") or "").strip().casefold()
    return bool(item.get("leader_watch_protected") or item.get("leader_signal") or item.get("leader_priority") or slot == "leader_interview")


def _prepare(item: dict) -> dict:
    out = enrich_source_priority(dict(item))
    profile = _match_pioneer(out)
    if profile:
        out = attach_pioneer_signal(out, profile)
        tensions = tension_for_person(str(profile.get("name") or ""))
        if tensions:
            out["epistemic_tension_id"] = tensions[0]["id"]
    return out


def mission_score(item: dict) -> float:
    item.update(_prepare(item))
    text = _text(item)
    area = classify_area(item)
    tier = _source_tier(item)
    base = float(item.get("editorial_score", 0) or 0) + float(item.get("signal_score", 0) or 0) * 0.4
    frontier = min(14.0, _hits(text, FRONTIER) * 2.0)
    trend = min(9.0, _hits(text, TREND) * 1.5)
    evidence = {1: 10.0, 2: 6.0, 3: -6.0}.get(tier, -6.0)
    future = 7.0 if area in {"convergence", "mind_cognition", "future_governance"} else 0.0
    research = 6.0 if str(item.get("content_type") or "").lower() in {"research", "paper", "study", "preprint"} else 0.0
    interview = 4.0 if _is_interview(item) else 0.0
    deep = float(item.get("deep_source_weight", 0) or 0) * 8.0
    pioneer = min(14.0, float(item.get("pioneer_priority", 0) or 0) * 0.12)
    tension = 5.0 if item.get("epistemic_tension_id") else 0.0
    low = min(20.0, _hits(text, LOW_SIGNAL) * 8.0)
    if tier == 3: low += 10.0
    score = base + frontier + trend + evidence + future + research + interview + deep + pioneer + tension - low
    item["mission_area"] = area
    item["source_tier_effective"] = tier
    item["mission_score"] = round(score, 2)
    item["frontier_signal"] = frontier > 0
    item["future_signal"] = future > 0 or trend >= 3
    item["analytical_anchor"], item["analytical_anchor_reasons"] = analytical_anchor(item)
    return score


def select_mission_portfolio(items: list[dict], max_posts: int = 4, history: list[dict] | None = None,
                             max_per_source: int = 2, max_per_type: int = 2) -> list[dict]:
    """Select a diverse high-signal portfolio; routine stories need an analytical anchor."""
    candidates = []
    for raw in items or []:
        item = dict(raw)
        score = mission_score(item)
        if score < 5 or (_source_tier(item) >= 3 and not _is_protected_leader(item)) or not item.get("analytical_anchor"):
            continue
        candidates.append(item)

    ranked = sorted(candidates, key=lambda x: (float(x.get("mission_score", 0)), str(x.get("published", ""))), reverse=True)
    if not ranked:
        return []

    selected: list[dict] = []
    sources: set[str] = set()
    areas: Counter = Counter()
    types: Counter = Counter()
    leaders: set[str] = set()

    def source_key(x): return str(x.get("source") or x.get("source_domain") or "unknown").strip().casefold()
    def add(x, reason, protected=False):
        s = source_key(x)
        ctype = str(x.get("content_type") or "news").lower()
        if not protected and s in sources: return False
        if protected:
            lk = _leader_key(x)
            if lk in leaders: return False
            leaders.add(lk)
        if types[ctype] >= max_per_type: return False
        if not protected and sum(1 for y in selected if source_key(y) == s) >= max_per_source: return False
        selected.append(x); sources.add(s); areas[str(x.get("mission_area"))] += 1; types[ctype] += 1
        x["mission_selection_reason"] = reason
        x.setdefault("editorial_slot", "fallback")
        x.setdefault("selection_reason", reason)
        return True

    protected = [x for x in ranked if _is_protected_leader(x)]
    protected.sort(key=lambda x: (int(x.get("source_tier_effective", _source_tier(x))), -int(x.get("leader_priority") or x.get("pioneer_priority") or 0), 1 if _is_interview(x) else 0, float(x.get("mission_score") or 0)), reverse=False)
    # Pick the best source for each leader first; only fall back to a weaker source if no stronger source exists.
    best_by_leader = {}
    for x in protected:
        key = _leader_key(x)
        if key not in best_by_leader:
            best_by_leader[key] = x
    for x in best_by_leader.values():
        if add(x, "protected_leader", protected=True):
            x["leader_watch_protected"] = True
            x["leader_signal"] = True
            x["leader_interview"] = str(x.get("editorial_slot") or "").casefold() == "leader_interview"

    regular_cap = max_posts
    while len([x for x in selected if not _is_protected_leader(x)]) < regular_cap:
        before = len(selected)
        for label, pool in [
            ("research_evidence", [x for x in ranked if not _is_protected_leader(x) and str(x.get("content_type") or "").lower() in {"research","paper","study","preprint"}]),
            ("ai_emerging_technology_convergence", [x for x in ranked if not _is_protected_leader(x) and x.get("mission_area") == "convergence"]),
            ("mind_cognition_future_signal", [x for x in ranked if not _is_protected_leader(x) and x.get("mission_area") in {"mind_cognition","future_governance"}]),
            ("frontier_pioneer", [x for x in ranked if not _is_protected_leader(x) and (x.get("pioneer_name") or x.get("mission_area") == "ai_core")]),
        ]:
            if len([x for x in selected if not _is_protected_leader(x)]) >= regular_cap: break
            for candidate in pool:
                if add(candidate, label): break

        if len(selected) == before:
            break

    print("[Mission Portfolio] " + " | ".join(f"{i+1}:{x.get('mission_area')}:{x.get('source')}:{x.get('mission_score')}:{x.get('mission_selection_reason')}" for i, x in enumerate(selected)), flush=True)
    print(f"[Mission Portfolio] sources={len(sources)} areas={dict(areas)} types={dict(types)} protected_leaders={len(leaders)}", flush=True)
    return selected
