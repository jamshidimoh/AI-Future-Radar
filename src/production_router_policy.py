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
    """Install production failover and quality-first chain once."""
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return

    original_disable = router._disable
    original_chain = getattr(router, "_ORIGINAL_GET_QUALITY_CHAIN", router.get_quality_chain)

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

    def production_chain():
        chain = build_production_chain(router)
        if chain:
            names = ", ".join(name for name, _ in chain)
            print(f"[Production Model Registry] chain={names}", flush=True)
            return chain
        return original_chain()

    router._disable = production_disable
    router._ORIGINAL_DISABLE = original_disable
    router._ORIGINAL_GET_QUALITY_CHAIN = original_chain
    router.get_quality_chain = production_chain
    router._PRODUCTION_POLICY_APPLIED = True
