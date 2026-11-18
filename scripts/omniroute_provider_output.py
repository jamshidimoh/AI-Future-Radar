"""Normalize OmniRoute provider-list output without trusting terminal formatting."""
# ruff: noqa: I001  # Keep the small stdlib import block in conventional order.
import json
import re
import sys
from typing import Any
from pathlib import Path


_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def parse_provider_list(raw: str) -> list[dict[str, Any]]:
    """Extract a JSON provider list from plain or ANSI-decorated CLI output."""
    cleaned = _ANSI_ESCAPE.sub("", raw).lstrip("\ufeff").strip()
    decoder = json.JSONDecoder()
    payload: Any = None
    for index, char in enumerate(cleaned):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned[index:])
            break
        except json.JSONDecodeError:
            continue

    if isinstance(payload, list):
        providers = payload
    elif isinstance(payload, dict) and isinstance(payload.get("providers"), list):
        providers = payload["providers"]
    else:
        raise ValueError("provider-list output did not contain a JSON array")

    if any(not isinstance(provider, dict) for provider in providers):
        raise ValueError("provider-list JSON contained a non-object entry")
    return providers


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: omniroute_provider_output.py PATH", file=sys.stderr)
        return 2
    try:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
        providers = parse_provider_list(raw)
    except (OSError, ValueError) as exc:
        # Never echo raw CLI output: it may contain provider credentials.
        print(f"[OmniRoute] provider-list output ignored: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(providers, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
