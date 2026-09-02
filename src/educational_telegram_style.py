"""Premium, RTL-safe Telegram renderer for educational posts."""
from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote

from education_quality import assert_publishable

RLI = "\u2067"
LRI = "\u2066"
PDI = "\u2069"
RLM = "\u200f"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
SHORT_DIVIDER = "──────────────"
# Keep the educational renderer aligned with the canonical single-message
# delivery guard. This leaves no gap where the renderer can produce a message
# that telegram_single_delivery.py will reject at the same 3900-char budget.
MAX_MESSAGE = 3900
# Expanded educational budgets are intentionally limited to the educational
# renderer. The renderer still has deterministic fallback budgets for Telegram's
# single-message ceiling.
MAX_DEFINITION = 650
MAX_SIMPLE = 380
MAX_RELATION = 360
MAX_EXAMPLE = 380
MAX_TAKEAWAY = 240


def _e(value: Any, quote: bool = False) -> str:
    return html.escape(str(value or "").strip(), quote=quote)


def _fit(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: max(1, limit - 1)].rsplit(" ", 1)[0].rstrip()
    return cut + "…"


def _latin_runs(text: str) -> str:
    parts = re.split(r"(<[^>]+>)", str(text or ""))
    out: list[str] = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            out.append(part)
            continue
        out.append(re.sub(r"[A-Za-z][A-Za-z0-9@._+/#:&'’(),\-\s]*", lambda m: f"{LRI}{m.group(0).rstrip()}{PDI}{m.group(0)[len(m.group(0).rstrip()):]}", part))
    return "".join(out)


def _rtl(text: str) -> str:
    return f"{RLI}{RLM}{_latin_runs(text)}{RLM}{PDI}"


def _ltr(text: str) -> str:
    return f"{LRI}{text}{PDI}"


def _english(text: str) -> str:
    return f"{LRI}{_e(text)}{PDI}"


def _term_label(term: str, fa: str) -> str:
    return f"{_e(fa)}\n{_english(term)}" if fa and term else _e(fa or term)


def _source_lines(item: dict[str, Any], limit: int = 3) -> list[str]:
    out: list[str] = []
    for source in (item.get("education_sources") or [])[:limit]:
        name = str(source.get("name") or "").strip()
        url = _e(source.get("url", ""), quote=True)
        year = str(source.get("year") or "").strip()
        if not name or not url:
            continue
        out.append(_rtl(f"• <a href=\"{url}\">{_e(name)}</a>{f' · {year}' if year else ''}"))
    return out


def _boxed_section(icon: str, title: str, body: str) -> list[str]:
    return [_rtl(f"<b>{icon} {title}</b>"), "", _rtl(f"<blockquote>{body}</blockquote>")]


def _concept(number: str, label: str, definition: str, simple: str) -> list[str]:
    return [_rtl(f"<b>{number} {label}</b>"), "", _rtl(f"<blockquote>{definition}</blockquote>"), "", _rtl("💡 <b>به زبان ساده</b>"), _rtl(simple)]


def _chatgpt_prompt(item: dict[str, Any]) -> str:
    a = _e(item.get("education_term_a_fa")) or _e(item.get("education_term_a"))
    b = _e(item.get("education_term_b_fa")) or _e(item.get("education_term_b"))
    return f"درباره «{a}» و «{b}» آموزش عمیق اما ساده فارسی ارائه کن؛ تعریف علمی، سازوکار، مثال، کاربرد، محدودیت و تفاوت‌ها را توضیح بده و فقط از منابع معتبر ۲۰۲۵+ استفاده کن."


def _chatgpt_cta(item: dict[str, Any]) -> list[str]:
    url = f"https://chatgpt.com/?q={quote(_chatgpt_prompt(item), safe='')}"
    return [_rtl(f"<blockquote>🧠 <a href=\"{url}\"><b>آموزش عمیق‌تر با ChatGPT</b></a></blockquote>")]


def _assert_rtl_contract(lines: list[str]) -> None:
    for line in lines:
        if not line or line in {DIVIDER, SHORT_DIVIDER}:
            continue
        if not (line.startswith(RLI) and line.endswith(PDI)):
            raise ValueError(f"Educational RTL contract violated: {line[:80]!r}")


def _render(item: dict[str, Any], budgets: tuple[int, int, int, int, int], include_sources: bool = True) -> tuple[list[str], str]:
    a_label = _term_label(_e(item.get("education_term_a")), _e(item.get("education_term_a_fa")))
    b_label = _term_label(_e(item.get("education_term_b")), _e(item.get("education_term_b_fa")))
    number = int(item.get("education_number", item.get("education_id", 0)) or 0)
    definition, simple, relation, example, takeaway = budgets
    lines: list[str] = [_rtl(f"<b>🧠 درس {number:02d}</b>"), DIVIDER, ""]
    lines.extend(_concept("۱.", a_label, _e(_fit(item.get("term_a_definition"), definition)), _e(_fit(item.get("term_a_simple"), simple))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_concept("۲.", b_label, _e(_fit(item.get("term_b_definition"), definition)), _e(_fit(item.get("term_b_simple"), simple))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_boxed_section("🔗", "رابطه دو مفهوم", _e(_fit(item.get("relationship"), relation))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_boxed_section("🧩", "مثال واقعی", _e(_fit(item.get("example"), example))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_boxed_section("📌", "نکته کلیدی", _e(_fit(item.get("takeaway"), takeaway))))
    lines.extend(["", DIVIDER, ""])
    lines.extend(_chatgpt_cta(item))
    sources = _source_lines(item, 3 if include_sources else 0)
    if sources:
        lines.extend(["", DIVIDER, "", _rtl("<b>📚 منابع منتخب</b>"), "", *sources])
    _assert_rtl_contract(lines)
    return lines, "\n".join(lines).strip()


def format_educational_post(item: dict[str, Any]) -> str:
    verified = assert_publishable(item, item.get("education_sources") or [], minimum_score=85)
    item["education_sources"] = verified
    budget_sets = (
        (MAX_DEFINITION, MAX_SIMPLE, MAX_RELATION, MAX_EXAMPLE, MAX_TAKEAWAY),
        (480, 280, 270, 290, 180),
        (400, 220, 220, 240, 150),
        (330, 180, 180, 200, 120),
    )
    for budgets in budget_sets:
        for include_sources in (True, False):
            _, result = _render(item, budgets, include_sources=include_sources)
            if len(result) <= MAX_MESSAGE:
                return result
    lines, _ = _render(item, budget_sets[-1], include_sources=False)
    kept: list[str] = []
    for line in lines:
        candidate = "\n".join(kept + [line]).strip()
        if len(candidate) <= MAX_MESSAGE:
            kept.append(line)
        else:
            break
    result = "\n".join(kept).strip()
    if len(result) > MAX_MESSAGE:
        raise ValueError(f"Educational post exceeds single-message budget: {len(result)} characters")
    return result
