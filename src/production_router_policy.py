"""Production-only LLM router policy.

A quota on one model should not suppress sibling models in the same provider
family. Authentication/configuration failures still disable the provider family.
"""
from __future__ import annotations

# Keep this module importable both as ``src.production_router_policy`` and as
# ``production_router_policy`` when ``src`` is placed directly on sys.path by
# the test/legacy execution paths.
try:
    from . import llm_router_light as router
except ImportError:  # pragma: no cover - compatibility for direct src imports
    import llm_router_light as router


def apply() -> None:
    """Install the production failover policy once."""
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return

    original_disable = router._disable

    def production_disable(name: str, reason: str) -> None:
        family = router._provider_family(name)
        router._DISABLED.add(name)
        # Quota/rate-limit is model-level unless the provider itself is
        # demonstrably unavailable. This preserves sibling-model fallback.
        if reason == "permanent":
            router._DISABLED_FAMILIES.add(family)
        print(
            f"[Light Router] disabled={name} family={family} reason={reason} "
            f"scope={'family' if reason == 'permanent' else 'model'}",
            flush=True,
        )

    router._disable = production_disable
    router._PRODUCTION_POLICY_APPLIED = True
    router._ORIGINAL_DISABLE = original_disable
