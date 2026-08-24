from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import period_ranked_pipeline as pipeline
import main as main_module
from src.editorial import filter_ai_relevance as wrapped_filter

_original = main_module.filter_ai_relevance

def debug_filter(items, ai_keywords=None):
    seq=list(items or [])
    print(f'[AI Gate Runtime] module={getattr(_original,"__module__","?")} file={getattr(getattr(_original,"__code__",None),"co_filename","?")}',flush=True)
    print(f'[AI Gate Runtime] input={len(seq)} titles={sum(bool(str(x.get("title") or "").strip()) for x in seq)} summaries={sum(bool(str(x.get("summary") or "").strip()) for x in seq)} evidence={sum(bool(str(x.get("evidence_text") or "").strip()) for x in seq)} keywords={len(ai_keywords or [])}',flush=True)
    for i,x in enumerate(seq[:12],1):
        print(f'[AI Gate Sample {i}] title={str(x.get("title") or "")[:160]!r} summary={str(x.get("summary") or "")[:220]!r} evidence={str(x.get("evidence_text") or "")[:220]!r} source={str(x.get("source") or "")[:100]!r}',flush=True)
    out=_original(seq,ai_keywords)
    print(f'[AI Gate Runtime] output={len(out)}',flush=True)
    return out

main_module.filter_ai_relevance=debug_filter
pipeline.main(pipeline._pipeline.main if False else None) if False else None
import production_resilient_runner
if __name__=='__main__':
    raise SystemExit(production_resilient_runner.main())
