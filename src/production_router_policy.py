"""Production-only LLM router policy.

A quota on one model should not suppress sibling models in the same provider
family. Authentication/configuration failures still disable the provider family.
The policy also normalizes the historical top-level/package import aliases so
production cannot silently run with two independent router module instances.
"""
from __future__ import annotations

import importlib
import sys


def _load_router():
    """Return one shared llm_router_light module for all supported import paths."""
    router = sys.modules.get("llm_router_light") or sys.modules.get("src.llm_router_light")
    if router is None:
        try:
            router = importlib.import_module("llm_router_light")
        except ImportError:
            router = importlib.import_module("src.llm_router_light")

    # Production historically mixes ``llm_router_light`` and
    # ``src.llm_router_light`` imports. Make both names resolve to the same
    # module object so stateful routing policy is applied exactly once.
    sys.modules.setdefault("llm_router_light", router)
    sys.modules.setdefault("src.llm_router_light", router)
    return router


def apply() -> None:
    """Install the production failover policy once on the shared router."""
    router = _load_router()
    if getattr(router, "_PRODUCTION_POLICY_APPLIED", False):
        return

    original_disable = router._disable

    def production_disable(name: str, reason: str) -> None:
        family = router._provider_family(name)
        router._DISABLED.add(name)
        # Quota/rate-limit is model-level. Permanent authentication/configuration
        # failures are family-level. This preserves sibling-model failover.
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
