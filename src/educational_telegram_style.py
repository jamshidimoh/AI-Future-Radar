"""Premium, RTL-safe Telegram renderer for educational posts."""
from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote

from education_quality import assert_publishable

# Directional isolates. Every visual row gets its own RTL container; Latin runs
# are isolated inside that container so the first English token cannot flip the row.
RLI = "\u2067"
LRI = "\u2066"
PDI = "\u2069"
RLM = "\u200f"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
SHORT_DIVIDER = "──────────────"
# Keep the rendered lesson safely below Telegram's 4096-character limit.
MAX_DEFINITION = 580
MAX_SIMPLE = 350
MAX_RELATION = 340
MAX_EXAMPLE = 360
MAX_TAKEAWAY = 220


def _e(value: Any, quote: bool = False) -> str:
    return html.escape(str(value or "").strip(), quote=quote)


def _fit(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip()
    return cut + "…"


def _latin_runs(text: str) -> str:
    """Isolate Latin runs while preserving HTML tags and their direction."""
    parts = re.split(r"(<[^>]+>)", str(text or ""))
    out: list[str] = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            out.append(part)
            continue
        out.append(
            re.sub(
                r"[A-Za-z][A-Za-z0-9@._+/#:&'’(),\-\s]*",
                lambda m: f"{LRI}{m.group(0).rstrip()}{PDI}{m.group(0)[len(m.group(0).rstrip()):]}",
                part,
            )
        )
    return "".join(out)


def _rtl(text: str) -> str:
    """Create one independent RTL visual row/paragraph."""
    return f"{RLI}{RLM}{_latin_runs(text)}{RLM}{PDI}"


def _ltr(text: str) -> str:
    """Create a fully isolated LTR row, used only where the whole row is Latin."""
    return f"{LRI}{text}{PDI}"


def _english(text: str) -> str:
    return f"{LRI}{_e(text)}{PDI}"


def _term_label(term: str, fa: str) -> str:
    if fa and term:
        return f"{_e(fa)}\n{_english(term)}"
    return _e(fa or term)


def _source_lines(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for source in (item.get("education_sources") or [])[:3]:
        name = str(source.get("name") or "").strip()
        url = _e(source.get("url", ""), quote=True)
        year = str(source.get("year") or "").strip()
        if not name or not url:
            continue
        year_part = f" · {year}" if year else ""
        name_html = _e(name)
        row = f"• <a href=\"{url}\">{name_html}</a>{year_part}"
        out.append(_rtl(row))
    return out


def _boxed_section(icon: str, title: str, body: str) -> list[str]:
    return [_rtl(f"<b>{icon} {title}</b>"), "", _rtl(f"<blockquote>{body}</blockquote>")]


def _concept(number: str, label: str, definition: str, simple: str) -> list[str]:
    return [
        _rtl(f"<b>{number} {label}</b>"),
        "",
        _rtl(f"<blockquote>{definition}</blockquote>"),
        "",
        _rtl("💡 <b>به زبان ساده</b>"),
        _rtl(simple),
    ]


def _chatgpt_prompt(item: dict[str, Any]) -> str:
    a = _e(item.get("education_term_a_fa")) or _e(item.get("education_term_a"))
    b = _e(item.get("education_term_b_fa")) or _e(item.get("education_term_b"))
    return (
        "درباره «{a}» و «{b}» آموزش عمیق اما ساده فارسی ارائه کن؛ تعریف علمی، سازوکار، "
        "مثال، کاربرد، محدودیت و تفاوت‌ها را توضیح بده و فقط از منابع معتبر ۲۰۲۵+ استفاده کن."
    ).format(a=a, b=b)


def _chatgpt_cta(item: dict[str, Any]) -> list[str]:
    url = f"https://chatgpt.com/?q={quote(_chatgpt_prompt(item), safe='')}"
    return [_rtl(f"<blockquote>🧠 <a href=\"{url}\"><b>آموزش عمیق‌تر با ChatGPT</b></a></blockquote>")]


def _assert_rtl_contract(lines: list[str]) -> None:
    """Fail closed if a non-empty visual row is not wrapped in an RTL isolate."""
    for line in lines:
        if not line or line in {DIVIDER, SHORT_DIVIDER}:
            continue
        if not (line.startswith(RLI) and line.endswith(PDI)):
            raise ValueError(f"Educational RTL contract violated: {line[:80]!r}")


def format_educational_post(item: dict[str, Any]) -> str:
    verified = assert_publishable(item, item.get("education_sources") or [], minimum_score=85)
    item["education_sources"] = verified

    a_label = _term_label(_e(item.get("education_term_a")), _e(item.get("education_term_a_fa")))
    b_label = _term_label(_e(item.get("education_term_b")), _e(item.get("education_term_b_fa")))
    number = int(item.get("education_number", item.get("education_id", 0)) or 0)

    lines: list[str] = [
        _rtl(f"<b>🧠 درس {number:02d}</b>"),
        DIVIDER,
        "",
    ]
    lines.extend(_concept("۱.", a_label, _e(_fit(item.get("term_a_definition"), MAX_DEFINITION)), _e(_fit(item.get("term_a_simple"), MAX_SIMPLE))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_concept("۲.", b_label, _e(_fit(item.get("term_b_definition"), MAX_DEFINITION)), _e(_fit(item.get("term_b_simple"), MAX_SIMPLE))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_boxed_section("🔗", "رابطه دو مفهوم", _e(_fit(item.get("relationship"), MAX_RELATION))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_boxed_section("🧩", "مثال واقعی", _e(_fit(item.get("example"), MAX_EXAMPLE))))
    lines.extend(["", SHORT_DIVIDER, ""])
    lines.extend(_boxed_section("📌", "نکته کلیدی", _e(_fit(item.get("takeaway"), MAX_TAKEAWAY))))
    lines.extend(["", DIVIDER, ""])
    lines.extend(_chatgpt_cta(item))

    sources = _source_lines(item)
    if sources:
        lines.extend(["", DIVIDER, "", _rtl("<b>📚 منابع منتخب</b>"), "", *sources])

    _assert_rtl_contract(lines)
    result = "\n".join(lines).strip()
    if len(result) > 4090:
        raise ValueError(f"Educational post exceeds single-message budget: {len(result)} characters")
    return result
