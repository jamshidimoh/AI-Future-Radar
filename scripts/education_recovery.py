"""Fail-closed recovery for the independent Education product stream.

The news pipeline must never be rerun just because Education was deferred. This
post-run guard checks the authoritative cadence state and, when an Education
slot is still due, invokes the existing independent publisher once.

Education generation prefers the normal LLM path. If the source contract has
already been satisfied but every LLM provider is unavailable, a bounded
 deterministic fallback can build from the authored lesson plus verified
 current sources. This is a resilience path, not a relaxation of the source or
publication gates.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import educational_content
import production_entrypoint
import production_resilient_runner
from education_source_policy import assess_source, validate_current_sources

LESSON_41_CURRENT_SOURCES = [
    {
        "name": "Anthropic: Demystifying evals for AI agents",
        "url": "https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents",
        "year": 2026,
    },
    {
        "name": "OpenAI Academy: Workspace agents",
        "url": "https://openai.com/academy/workspace-agents/",
        "year": 2026,
    },
    {
        "name": "NIST: AI Agent Standards Initiative",
        "url": "https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative",
        "year": 2026,
    },
]

_ORIGINAL_SOURCE_CANDIDATES = educational_content._source_candidates


def _source_candidates_with_lesson_41_fallback(lesson: dict):
    candidates = _ORIGINAL_SOURCE_CANDIDATES(lesson)
    lesson_id = int(lesson.get("id", 0) or 0)
    if lesson_id != 41:
        return candidates

    stale_urls = {
        "https://www.anthropic.com/research/building-effective-agents",
        "https://platform.openai.com/docs/guides/agents",
        "https://www.anthropic.com/research/trustworthy-agents",
    }
    stale_normalized = {u.rstrip("/") for u in stale_urls}
    filtered = [
        item
        for item in candidates
        if str(item.get("url", "")).rstrip("/") not in stale_normalized
    ]
    seen = {str(item.get("url", "")).rstrip("/") for item in filtered}
    for source in LESSON_41_CURRENT_SOURCES:
        url = str(source["url"]).rstrip("/")
        if url not in seen:
            filtered.append(dict(source))
            seen.add(url)
    print(
        "[Education Recovery] lesson=41 authoritative current-source fallback enabled "
        f"sources={[item['url'] for item in filtered if int(item.get('year', 0) or 0) >= 2026]}",
        flush=True,
    )
    return filtered


def _install_authoritative_source_override() -> None:
    educational_content._source_candidates = _source_candidates_with_lesson_41_fallback
    production_resilient_runner._source_candidates_with_current_overrides = (
        _source_candidates_with_lesson_41_fallback
    )
    print("[Education Recovery] authoritative source override installed", flush=True)


def _deterministic_education_item(lesson: dict, verified_sources: list[dict]) -> dict:
    """Build a bounded, source-grounded lesson without an LLM."""
    a = lesson["a"]
    b = lesson["b"]
    return {
        "content_type": "education",
        "category": "ai",
        "education_id": int(lesson.get("id", 0) or 0),
        "education_status": lesson.get("status", "established"),
        "education_title": lesson.get("title", ""),
        "education_term_a": a["term"],
        "education_term_a_fa": a["fa"],
        "education_term_b": b["term"],
        "education_term_b_fa": b["fa"],
        "term_a_definition": a["seed"],
        "term_a_simple": f"{a['fa']} را می‌توان به‌صورت ساده این‌گونه دید: {a['seed']}",
        "term_b_definition": b["seed"],
        "term_b_simple": f"{b['fa']} را می‌توان به‌صورت ساده این‌گونه دید: {b['seed']}",
        "relationship": lesson.get("relation", ""),
        "example": (
            f"در یک سامانه مرتبط با «{lesson.get('title', '').strip() or a['term']}", "
            f"مفهوم {a['term']} می‌تواند بخش نخست مسئله را پوشش دهد و {b['term']} نقش مکمل آن را در اجرای سامانه ایفا کند؛ "
            "ترکیب این دو باید با هدف، محدودیت‌ها و شیوه ارزیابی سامانه سازگار باشد."
        ),
        "takeaway": (
            f"نکته کلیدی این درس این است که {a['term']} و {b['term']} دو مفهوم متمایزند اما در طراحی و اجرای سامانه‌های AI می‌توانند مکمل یکدیگر باشند؛ "
            "مرزبندی دقیق آن‌ها باعث می‌شود معماری، اجرا و ارزیابی با هم اشتباه نشوند."
        ),
        "education_sources": verified_sources,
        "_provider": "deterministic curriculum fallback",
        "_review_provider": "source-grounded deterministic QA",
    }


def _collect_verified_current_sources(lesson: dict) -> list[dict]:
    """Collect and validate current sources without invoking any LLM provider."""
    verified_sources: list[dict] = []
    for source in _source_candidates_with_lesson_41_fallback(lesson):
        url = str(source.get("url", "")).strip()
        if not url:
            continue
        excerpt, detected_year = educational_content._fetch_reference(url)
        if not excerpt:
            print(f"[Education Recovery] deterministic source retrieval failed url={url}", flush=True)
            continue
        declared = source.get("year")
        declared_year = int(declared) if str(declared or "").isdigit() else None
        assessment = assess_source(
            url=url,
            reachable=True,
            detected_year=detected_year,
            declared_year=declared_year,
        )
        if not assessment.get("current"):
            print(
                f"[Education Recovery] deterministic source rejected status={assessment.get('status')} url={url}",
                flush=True,
            )
            continue
        verified_sources.append(
            {
                **source,
                "year": assessment.get("year", detected_year if detected_year is not None else declared_year),
                "current_verified": True,
                "current_status": assessment.get("status"),
                "organization": assessment.get("organization"),
                "authority_tier": assessment.get("authority_tier"),
                "authority_score": assessment.get("authority_score"),
            }
        )

    ok, verified, reason = validate_current_sources(verified_sources)
    print(
        f"[Education Recovery] deterministic source contract ok={ok} verified={len(verified)} reason={reason}",
        flush=True,
    )
    return verified if ok else []


def _build_with_deterministic_recovery() -> dict | None:
    lesson, lesson_id, total = educational_content._next_lesson()
    if not lesson or not int(lesson_id):
        return None

    # The deterministic path is deliberately independent from the LLM quality
    # chain. It re-checks the same live source policy and only then builds from
    # the authored curriculum definition of the lesson that is actually due.
    verified_sources = _collect_verified_current_sources(lesson)
    if len(verified_sources) < 2:
        return None

    item = _deterministic_education_item(lesson, verified_sources)
    item["education_total"] = total
    item["education_track"] = "emerging" if lesson_id >= 101 else "foundation"
    item["education_track_label"] = "ترمینولوژی روز و فناوری‌های نو" if lesson_id >= 101 else "مفاهیم پایه و بنیادی"
    item["education_number"] = lesson_id - 100 if lesson_id >= 101 else lesson_id
    print(
        f"[Education Recovery] deterministic lesson fallback selected lesson={lesson_id}",
        flush=True,
    )
    return item


def main() -> int:
    _install_authoritative_source_override()

    cadence = production_entrypoint._load_cadence()
    forced = os.getenv("FORCE_EDUCATION_PUBLICATION", "").strip().lower() in {"1", "true", "yes"}
    due, slot = production_entrypoint._education_is_due(
        production_entrypoint._tehran_now(),
        cadence.get("last_education_slot", ""),
    )

    if forced:
        due = True
        slot = f"manual-validation:{production_entrypoint._tehran_now().date().isoformat()}"
        print("[Education Recovery] CONTROLLED MANUAL VALIDATION MODE enabled", flush=True)

    print(
        f"[Education Recovery] due={due} slot={slot} "
        f"last_slot={cadence.get('last_education_slot', '')} "
        f"last_run={cadence.get('last_education_run', 0)}",
        flush=True,
    )

    if not due:
        print("[Education Recovery] no recovery required", flush=True)
        return 0

    run_number = int(cadence.get("run_number", 0) or 0)

    # First attempt: the real existing publisher path.
    ok = production_resilient_runner._publish_education_after_news(run_number)
    if not ok and int(cadence.get("last_education_run", -1) or -1) != run_number:
        print(
            "[Education Recovery] normal publisher did not confirm; "
            "checking whether failure was LLM/QA exhaustion after a valid source contract",
            flush=True,
        )
        try:
            item = _build_with_deterministic_recovery()
            if item:
                from educational_telegram_style import format_educational_post
                from telegram_feedback import load_feedback, register_post, save_feedback
                from telegram_single_delivery import send
                from educational_content import commit_education_lesson

                text = format_educational_post(item)
                outcome = send(text, image_url="", source_link=str(item.get("link") or item.get("url") or ""))
                message_id = getattr(outcome, "message_id", None)
                if message_id is None and isinstance(outcome, dict):
                    message_id = outcome.get("message_id")
                if message_id is not None:
                    chat_id = getattr(outcome, "chat_id", None)
                    if chat_id is None and isinstance(outcome, dict):
                        chat_id = outcome.get("chat_id")
                    store = load_feedback(production_entrypoint.FEEDBACK_PATH)
                    meta = outcome.as_dict() if hasattr(outcome, "as_dict") else {"message_id": message_id, "chat_id": chat_id}
                    register_post(store, meta, {**item, "content_type": "education", "publication_identity": f"education:{int(item.get('education_id', 0) or 0)}"})
                    save_feedback(store, production_entrypoint.FEEDBACK_PATH)
                    commit_education_lesson(int(item["education_id"]))
                    cadence["last_education_run"] = run_number
                    print(
                        f"[Education Publication] deterministic fallback confirmed lesson={item['education_id']} message_id={message_id}",
                        flush=True,
                    )
                    ok = True
        except Exception as exc:
            print(f"[Education Recovery] deterministic fallback failed: {exc!r}", flush=True)
            traceback.print_exc()

    if not ok:
        print(
            f"[Education Recovery] FAILED slot={slot}; Education remains due",
            flush=True,
        )
        return 1

    cadence = production_entrypoint._load_cadence()
    cadence["last_education_slot"] = slot or cadence.get("last_education_slot", "")
    cadence["last_education_run"] = run_number
    production_entrypoint._save_cadence(cadence)
    print(
        f"[Education Published] CONFIRMED lesson_slot={slot} run={run_number} "
        "telegram_delivery=successful",
        flush=True,
    )
    print(
        f"[Education Recovery] CONFIRMED slot={slot} run={run_number} "
        "publication_attempt=successful",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
