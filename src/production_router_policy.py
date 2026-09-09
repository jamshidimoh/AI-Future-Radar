"""Production-only LLM routing policy.

Production uses the trusted free-model registry for deterministic quality-first
ordering. Quotas are model-scoped; authentication/configuration failures are
provider-family scoped. Gemini/Hugging Face remain optional emergency lanes.
"""
from __future__ import annotations

try:
    from . import llm_router_light as router
    from .free_model_registry import build_production_chain
except ImportError:  # pragma: no cover
    import llm_router_light as router
    from free_model_registry import build_production_chain


def apply() -> None:
    """Install production failover and cache the registry-derived chain.

    Do not monkey-patch public router functions: unit tests and other callers
    in the same Python process must retain the base router semantics. The
    production caller already resolves its chain through ``get_quality_chain``;
    replacing its cache is sufficient and naturally resets between runs/tests.
    """
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return

    def production_disable(name: str, reason: str) -> None:
        family = router._provider_family(name)
        router._DISABLED.add(name)
        if reason == "permanent":
            router._DISABLED_FAMILIES.add(family)
        scope = "family" if reason == "permanent" else "model"
        print(
            f"[Light Router] disabled={name} family={family} reason={reason} scope={scope}",
            flush=True,
        )

    router._disable = production_disable
    chain = build_production_chain(router)
    if chain:
        router._CHAIN_CACHE = list(chain)
        print(
            "[Production Model Registry] chain=" + ", ".join(name for name, _ in chain),
            flush=True,
        )
    router._PRODUCTION_POLICY_APPLIED = True
