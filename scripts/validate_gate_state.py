from __future__ import annotations

from pathlib import Path

REQUIRED = {
    "project",
    "mode",
    "current_gate",
    "status",
    "next_gate",
    "max_auto_retries",
    "production_promotion",
    "fail_closed",
    "last_verified_commit",
    "required_evidence",
}


def parse_state(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-") or line.endswith(":"):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    state = parse_state(Path("evolution/state.yaml"))
    missing = REQUIRED - state.keys()
    if missing:
        raise SystemExit(f"Missing state fields: {sorted(missing)}")
    gate = state["current_gate"]
    if gate not in {f"G{i}" for i in range(10)}:
        raise SystemExit(f"Invalid current_gate: {gate}")
    if state["production_promotion"] != "G9_ONLY":
        raise SystemExit("Production promotion must remain G9_ONLY")
    if state["fail_closed"].lower() != "true":
        raise SystemExit("fail_closed must remain true")
    print(f"Gate state valid: {gate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
