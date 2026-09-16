"""Canonical production launcher with a one-shot migration escape hatch."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_one_shot_migration() -> bool:
    trigger = ROOT / ".editorial_lanes_migration_trigger"
    migration = ROOT / "scripts" / "apply_technical_lane_isolation.py"
    if not trigger.exists() or not migration.exists():
        return False
    subprocess.run([sys.executable, str(migration)], check=True, cwd=ROOT)
    subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "production_entrypoint.py", "main.py", "src", "tests/test_technical_trend_lane.py", "tests/test_mind_interview_recall.py"],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_technical_trend_lane.py",
            "tests/test_mind_interview_recall.py",
            "tests/test_mission_coverage_priority.py",
            "tests/test_protected_editorial_lane.py",
            "tests/test_production_acceptance_guard.py",
            "tests/test_production_acceptance_contract.py",
            "tests/test_unified_editorial_selection.py",
        ],
        check=True,
        cwd=ROOT,
    )
    cleanup_paths = [
        trigger,
        migration,
        ROOT / ".github/workflows/z3_finalize_editorial_lanes.yml",
        ROOT / ".github/workflows/z9_apply_editorial_lanes.yml",
        ROOT / ".github/workflows/apply-editorial-lanes.yml",
    ]
    existing_cleanup = [str(path.relative_to(ROOT)) for path in cleanup_paths if path.exists()]
    if existing_cleanup:
        subprocess.run(["git", "rm", "-f", *existing_cleanup], check=True, cwd=ROOT)
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True, cwd=ROOT)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True, cwd=ROOT)
    subprocess.run(
        [
            "git",
            "add",
            "production_entrypoint.py",
            "scripts/production_with_protected_lane.py",
            "tests/test_technical_trend_lane.py",
            "tests/test_mind_interview_recall.py",
            "tests/test_mission_coverage_priority.py",
        ],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(["git", "commit", "-m", "fix: isolate technical trend publication lane"], check=True, cwd=ROOT)

    # A production state-persistence job may advance main between checkout and push.
    # Rebase the migration commit onto the current remote head before pushing.
    for _ in range(3):
        push = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT)
        if push.returncode == 0:
            return True
        subprocess.run(["git", "fetch", "origin", "main", "--depth=50"], check=True, cwd=ROOT)
        subprocess.run(["git", "rebase", "origin/main"], check=True, cwd=ROOT)
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, cwd=ROOT)
    return True


if __name__ == "__main__":
    if os.getenv("RADAR_DISABLE_ONE_SHOT_MIGRATION") != "1" and _run_one_shot_migration():
        raise SystemExit(0)
    import production_resilient_runner  # noqa: E402
    raise SystemExit(production_resilient_runner.main())
