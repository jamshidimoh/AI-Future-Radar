from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "msa_v1_telegram_recent.jsonl"

TECH = re.compile(r"\b(ai|artificial intelligence|machine learning|deep learning|llm|robot|robotics|quantum|bci|brain-computer|neuro|biotech|biology|automation|agentic|foundation model|multimodal|computer vision|future|cognition|consciousness)\b", re.I)
RESEARCH = re.compile(r"\b(research|study|paper|published|experiment|benchmark|results|findings|trial|dataset|model)\b", re.I)
BREAKTHROUGH = re.compile(r"\b(new|novel|breakthrough|first|state[- ]of[- ]the[- ]art|sota|launch|release|discovered|achieve|surpass)\b", re.I)
RISK = re.compile(r"\b(risk|failure|safety|threat|attack|outage|vulnerability|regulation|governance|bias)\b", re.I)
FUTURE = re.compile(r"\b(future|next|coming|forecast|2030|2035|2040|long[- ]term|emerging)\b", re.I)

def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

def tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]{3,}", text.lower()) if x not in {"the", "and", "for", "with", "from", "that", "this", "are", "you"}}

def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))

def classify(text: str) -> tuple[str, float, float, float, float]:
    tech = bool(TECH.search(text))
    research = bool(RESEARCH.search(text))
    breakthrough = bool(BREAKTHROUGH.search(text))
    risk = bool(RISK.search(text))
    future = bool(FUTURE.search(text))
    if risk and tech:
        signal = "S5_SYSTEMIC_RISK"
    elif research and breakthrough:
        signal = "S1_RESEARCH_BREAKTHROUGH"
    elif future and tech:
        signal = "S3_WEAK_SIGNAL"
    elif tech:
        signal = "S2_EMERGING_TECHNOLOGY"
    else:
        signal = "UNRELATED"
    relevance = min(1.0, (0.55 if tech else 0.0) + (0.15 if research else 0.0) + (0.15 if future else 0.0) + (0.15 if risk else 0.0))
    evidence = min(1.0, (0.55 if research else 0.0) + (0.25 if len(text) >= 240 else 0.0) + (0.20 if any(x in text.lower() for x in ["http", "doi", "paper", "study"]) else 0.0))
    importance = min(1.0, relevance * 0.55 + evidence * 0.25 + (0.20 if breakthrough or risk else 0.0))
    confidence = min(1.0, evidence * 0.75 + (0.25 if research else 0.0))
    return signal, relevance, evidence, importance, confidence

def main() -> int:
    rows = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        print("MSA_REAL_CORPUS_GATE=FAIL EMPTY_CORPUS")
        return 1

    exact = Counter(norm(r.get("text", "")) for r in rows)
    duplicate_rows = sum(n - 1 for n in exact.values() if n > 1)
    source_counts = Counter(r.get("channel", "") for r in rows)
    by_channel = defaultdict(list)
    for r in rows:
        by_channel[r.get("channel", "")].append(r)

    # Independent convergence is evidence-cluster convergence, not repost count.
    clusters: list[list[int]] = []
    token_rows = [tokens(r.get("text", "")) for r in rows]
    for i, t in enumerate(token_rows):
        if len(t) < 8:
            continue
        placed = False
        for cluster in clusters:
            if max(jaccard(t, token_rows[j]) for j in cluster) >= 0.34:
                cluster.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])

    annotated = []
    for r in rows:
        signal, relevance, evidence, importance, confidence = classify(r.get("text", ""))
        priority = (0.15 * relevance + 0.15 * importance + 0.12 * confidence + 0.18 * evidence + 0.10 * (1.0 if signal != "UNRELATED" else 0.0) + 0.10 * (1.0 / math.sqrt(max(1, source_counts[r.get("channel", "")]))))
        annotated.append((priority, relevance, evidence, importance, confidence, signal, r))
    annotated.sort(reverse=True, key=lambda x: x[0])

    signal_counts = Counter(x[5] for x in annotated)
    evidence_bands = Counter("HIGH" if x[2] >= .7 else "MEDIUM" if x[2] >= .4 else "LOW" for x in annotated)
    confidence_bands = Counter("HIGH" if x[4] >= .7 else "MEDIUM" if x[4] >= .4 else "LOW" for x in annotated)
    top20 = annotated[:20]
    top20_channels = len({x[6].get("channel") for x in top20})
    cross_channel_clusters = sum(1 for c in clusters if len({rows[i].get("channel") for i in c}) >= 2)
    traceable = sum(1 for x in annotated if x[6].get("url") and x[6].get("channel") and x[6].get("published_at"))
    substantive = sum(1 for x in annotated if len(x[6].get("text", "")) >= 120)

    digest = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    print(f"MSA_REAL_CORPUS records={len(rows)} channels={len(source_counts)}")
    print(f"MSA_REAL_CORPUS digest={digest}")
    print(f"MSA_DUPLICATE_ROWS={duplicate_rows}")
    print(f"MSA_SOURCE_DIVERSITY={len(source_counts)}/{20}")
    print(f"MSA_TRACEABILITY={traceable}/{len(rows)}")
    print(f"MSA_SUBSTANTIVE_TEXT={substantive}/{len(rows)}")
    print(f"MSA_EVIDENCE_BANDS={dict(evidence_bands)}")
    print(f"MSA_CONFIDENCE_BANDS={dict(confidence_bands)}")
    print(f"MSA_SIGNALS={dict(signal_counts)}")
    print(f"MSA_EVIDENCE_CLUSTERS={len(clusters)}")
    print(f"MSA_INDEPENDENT_CONVERGENCE_CLUSTERS={cross_channel_clusters}")
    print(f"MSA_TOP20_CHANNEL_DIVERSITY={top20_channels}/20")
    print("MSA_DECISION_RULES=importance_separate_from_confidence;convergence_not_repost_count;traceability_required;weak_signal_retained")

    gates = {
        "nonempty": len(rows) > 0,
        "all_20_channels_seen": len(source_counts) == 20,
        "traceability": traceable == len(rows),
        "no_duplicate_collapse_loss": duplicate_rows < len(rows),
        "multi_source_convergence_possible": cross_channel_clusters >= 1,
        "signal_taxonomy_active": any(k != "UNRELATED" for k in signal_counts),
        "importance_confidence_separate": any(abs(x[3] - x[4]) >= 0.15 for x in annotated),
    }
    for name, ok in gates.items():
        print(f"MSA_REAL_GATE {name}={'PASS' if ok else 'FAIL'}")
    passed = sum(gates.values())
    print(f"MSA_REAL_CORPUS_GATE={'PASS' if passed == len(gates) else 'FAIL'} passed={passed} total={len(gates)}")
    print("EMPIRICAL_SUPERIORITY=NOT_ESTABLISHED")
    print("BASELINE_COMPARISON=REQUIRES_SAME-CORPUS_LABELLED_DECISIONS")
    return 0 if passed == len(gates) else 1

if __name__ == "__main__":
    raise SystemExit(main())
