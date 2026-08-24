"""Temporary read-only AI Gate runtime probe."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import period_ranked_pipeline as pipeline
from src.ranking_audit import audit_selection
_original_filter = pipeline.filter_ai_relevance
_original_main = pipeline.main

def _debug_filter(items, ai_keywords=None):
    seq = list(items or [])
    module = getattr(_original_filter, "__module__", "<unknown>")
    filename = getattr(getattr(_original_filter, "__code__", None), "co_filename", "<unknown>")
    with_evidence = sum(bool(str(x.get("evidence_text") or "").strip()) for x in seq)
    with_summary = sum(bool(str(x.get("summary") or "").strip()) for x in seq)
    with_title = sum(bool(str(x.get("title") or "").strip()) for x in seq)
    print(f"[AI Gate Runtime] function_module={module} function_file={filename}", flush=True)
    print(f"[AI Gate Runtime] input={len(seq)} title={with_title} summary={with_summary} evidence_text={with_evidence} ai_keywords={len(ai_keywords or [])}", flush=True)
    for i, item in enumerate(seq[:8], 1):
        title = str(item.get("title") or "").replace("\n", " ")[:140]
        summary = str(item.get("summary") or "").replace("\n", " ")[:180]
        evidence = str(item.get("evidence_text") or "").replace("\n", " ")[:180]
        print(f"[AI Gate Sample {i}] title={title!r} summary={summary!r} evidence={evidence!r}", flush=True)
    out = _original_filter(seq, ai_keywords)
    print(f"[AI Gate Runtime] output={len(out)}", flush=True)
    return out

def _audited_main(hooks=None):
    merged = dict(hooks or {})
    original_select = merged.get("select_editorial")
    if original_select is None:
        return _original_main(hooks=merged)
    def audited_select(items, max_posts, max_per_source, max_per_type, policy):
        selected = original_select(items, max_posts, max_per_source, max_per_type, policy)
        audit_selection(selected)
        return selected
    merged["select_editorial"] = audited_select
    return _original_main(hooks=merged)

pipeline.filter_ai_relevance = _debug_filter
pipeline.main = _audited_main
import production_resilient_runner  # noqa: E402
if __name__ == "__main__":
    raise SystemExit(production_resilient_runner.main())
