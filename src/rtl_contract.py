"""Telegram RTL/LTR direction contract for Persian publication."""
from __future__ import annotations

RLI = "\u2067"
LRI = "\u2066"
PDI = "\u2069"
RLM = "\u200f"


def force_rtl_blocks(text: str) -> str:
    """Ensure every rendered Telegram block has an explicit RTL base direction.

    Existing Unicode isolates are preserved. Empty lines remain empty and Latin
    fragments are not rewritten here; send_telegram.py already isolates them.
    """
    raw = str(text or "")
    blocks = raw.splitlines()
    rendered = []
    for block in blocks:
        if not block:
            rendered.append("")
            continue
        if block.startswith(RLI) and block.endswith(PDI):
            rendered.append(block)
        else:
            rendered.append(f"{RLI}{RLM}{block}{PDI}")
    return "\n".join(rendered)
