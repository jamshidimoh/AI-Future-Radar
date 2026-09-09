"""Production-only LLM routing policy.

Production uses the trusted free-model registry for deterministic quality-first
ordering. Quotas are model-scoped in production; base-router compatibility
keeps quota family-scoped for legacy callers/tests. Authentication/configuration
failures remain provider-family scoped everywhere.
"""
from __future__ import annotations

try:
    from . import llm_router_light as router
    from .free_model_registry import build_production_chain
except ImportError:  # pragma: no cover
    import llm_router_light as router
    from free_model_registry import build_production_chain


def apply() -> None:
    """Enable production mode and cache the registry-derived chain.

    No functions are monkey-patched, so the policy cannot leak into unrelated
    callers in the same Python process. Tests can reset ``_PRODUCTION_POLICY_APPLIED``
    and ``_CHAIN_CACHE`` to restore the base router completely.
    """
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return

    chain = build_production_chain(router)
    if chain:
        router._CHAIN_CACHE = list(chain)
        print(
            "[Production Model Registry] chain=" + ", ".join(name for name, _ in chain),
            flush=True,
        )
    router._PRODUCTION_POLICY_APPLIED = True
