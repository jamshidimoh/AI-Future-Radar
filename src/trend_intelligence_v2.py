"""Publication-decoupled G1+G2 trend intelligence adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from src.trend_engine_v1 import build_trend_clusters
from src.trend_registry_v2 import load_registry, reconcile_registry, save_registry


def run_current_window(
    items: Sequence[Mapping[str, Any]],
    *,
    registry_path: str | Path,
    run_id: str,
    run_index: int,
    trend_config: Mapping[str, Any] | None = None,
    registry_config: Mapping[str, Any] | None = None,
    disconfirmed_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run G1 clustering and persist the G2 registry for one current window."""
    current_clusters = build_trend_clusters(items, trend_config)
    registry = load_registry(registry_path)
    updated = reconcile_registry(
        registry,
        current_clusters,
        run_id=run_id,
        run_index=run_index,
        config=registry_config,
        disconfirmed_ids=disconfirmed_ids,
    )
    save_registry(registry_path, updated)
    return {
        "run_id": str(run_id),
        "run_index": int(run_index),
        "clusters": current_clusters,
        "registry": updated,
    }
