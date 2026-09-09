"""Production-only LLM routing policy.

Production uses the trusted free-model registry for deterministic quality-first
ordering. Quotas are model-scoped in production; base-router compatibility
keeps quota family-scoped for legacy callers/tests. Authentication failures
remain provider-family scoped, while model permission/unavailability failures
remain model-scoped.
"""
from __future__ import annotations

import sys
from pathlib import Path

# The production application imports ``llm_router_light`` as a top-level module
# after main.py adds src/ to sys.path. Importing ``src.llm_router_light`` here
# creates a second module instance and silently bypasses the production chain.
# Resolve the exact canonical module used by summarization and grounding.
try:
    import llm_router_light as router
except ImportError:  # pragma: no cover
    src_dir = str(Path(__file__).resolve().parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    import llm_router_light as router

try:
    from .free_model_registry import build_production_chain
except ImportError:  # pragma: no cover
    from free_model_registry import build_production_chain


def apply() -> None:
    """Enable production mode on the canonical router module exactly once."""
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return

    chain = build_production_chain(router)
    if not chain:
        raise RuntimeError("Production model registry produced an empty provider chain")

    router._CHAIN_CACHE = list(chain)
    router._PRODUCTION_POLICY_APPLIED = True
    print(
        "[Production Model Registry] chain=" + ", ".join(name for name, _ in chain),
        flush=True,
    )
