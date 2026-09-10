"""Fail-closed recovery for the independent Education product stream."""
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
from education_dynamic_sources import rank_verified_sources
from education_source_policy import assess_source, validate_current_sources


def _deterministic_education_item(lesson: dict, verified_sources: list[dict]) -> dict:
    a, b = lesson["a"], lesson["b"]
    return {
        "content_type": "education", "category": "ai",
        "education_id": int(lesson.get("id", 0) or 0),
        "education_status": lesson.get("status", "established"),
        "education_title": lesson.get("title", ""),
        "education_term_a": a["term"], "education_term_a_fa": a["fa"],
        "education_term_b": b["term"], "education_term_b_fa": b["fa"],
        "term_a_definition": a["seed"],
        "term_a_simple": f"{a['fa']} را می‌توان به‌صورت ساده این‌گونه دید: {a['seed']}",
        "term_b_definition": b["seed"],
        "term_b_simple": f"{b['fa']} را می‌توان به‌صورت ساده این‌گونه دید: {b['seed']}",
        "relationship": lesson.get("relation", ""),
        "example": f"در یک سامانه مرتبط با «{lesson.get('title', '').strip() or a['term']}»، مفهوم {a['term']} می‌تواند بخش نخست مسئله را پوشش دهد و {b['term']} نقش مکمل آن را در اجرای سامانه ایفا کند؛ ترکیب این دو باید با هدف، محدودیت‌ها و شیوه ارزیابی سامانه سازگار باشد.",
        "takeaway": f"نکته کلیدی این درس این است که {a['term']} و {b['term']} دو مفهوم متمایزند اما در طراحی و اجرای سامانه‌های AI می‌توانند مکمل یکدیگر باشند؛ مرزبندی دقیق آن‌ها باعث می‌شود معماری، اجرا و ارزیابی با هم اشتباه نشوند.",
        "education_sources": verified_sources,
        "_provider": "deterministic curriculum fallback",
        "_review_provider": "source-grounded deterministic QA",
    }


def _collect_verified_current_sources(lesson: dict) -> list[dict]:
    """Probe the central dynamic candidate pool and fail over automatically."""
    verified_sources: list[dict] = []
    candidates = educational_content._source_candidates(lesson)
    print(
        f"[Education Recovery] dynamic source candidates lesson={int(lesson.get('id', 0) or 0)} count={len(candidates)}",
        flush=True,
    )
    for source in candidates:
        url = str(source.get("url", "")).strip()
        if not url:
            continue
        excerpt, detected_year = educational_content._fetch_reference(url)
        if not excerpt:
            print(f"[Education Recovery] dynamic source retrieval failed url={url}", flush=True)
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
                f"[Education Recovery] dynamic source rejected status={assessment.get('status')} url={url}",
                flush=True,
            )
            continue
        verified_sources.append({
            **source,
            "year": assessment.get("year", detected_year if detected_year is not None else declared_year),
            "current_verified": True,
            "current_status": assessment.get("status"),
            "organization": assessment.get("organization"),
            "authority_tier": assessment.get("authority_tier"),
            "authority_score": assessment.get("authority_score"),
        })

    ranked_sources = rank_verified_sources(verified_sources)
    ok, verified, reason = validate_current_sources(ranked_sources)
    print(
        f"[Education Recovery] dynamic source contract ok={ok} candidates={len(candidates)} verified={len(verified)} reason={reason}",
        flush=True,
    )
    return verified if ok else []


def _build_with_deterministic_recovery() -> dict | None:
    lesson, lesson_id, total = educational_content._next_lesson()
    if not lesson or not int(lesson_id):
        return None
    verified_sources = _collect_verified_current_sources(lesson)
    if len(verified_sources) < 2:
        return None
    item = _deterministic_education_item(lesson, verified_sources)
    item["education_total"] = total
    item["education_track"] = "emerging" if lesson_id >= 101 else "foundation"
    item["education_track_label"] = "ترمینولوژی روز و فناوری‌های نو" if lesson_id >= 101 else "مفاهیم پایه و بنیادی"
    item["education_number"] = lesson_id - 100 if lesson_id >= 101 else lesson_id
    print(f"[Education Recovery] deterministic lesson fallback selected lesson={lesson_id}", flush=True)
    return item


def main() -> int:
    cadence = production_entrypoint._load_cadence()
    forced = os.getenv("FORCE_EDUCATION_PUBLICATION", "").strip().lower() in {"1", "true", "yes"}
    due, slot = production_entrypoint._education_is_due(production_entrypoint._tehran_now(), cadence.get("last_education_slot", ""))
    if forced:
        due = True
        slot = f"manual-validation:{production_entrypoint._tehran_now().date().isoformat()}"
        print("[Education Recovery] CONTROLLED MANUAL VALIDATION MODE enabled", flush=True)
    print(f"[Education Recovery] due={due} slot={slot} last_slot={cadence.get('last_education_slot', '')} last_run={cadence.get('last_education_run', 0)}", flush=True)
    if not due:
        print("[Education Recovery] no recovery required", flush=True)
        return 0
    run_number = int(cadence.get("run_number", 0) or 0)
    ok = production_resilient_runner._publish_education_after_news(run_number)
    if not ok and int(cadence.get("last_education_run", -1) or -1) != run_number:
        print("[Education Recovery] normal publisher did not confirm; checking deterministic source-grounded fallback", flush=True)
        try:
            item = _build_with_deterministic_recovery()
            if item:
                from educational_telegram_style import format_educational_post
                from telegram_feedback import load_feedback, register_post, save_feedback
                from telegram_single_delivery import send
                from educational_content import commit_education_lesson
                text = format_educational_post(item)
                outcome = send(text, image_url="", source_link=str(item.get("link") or item.get("url") or ""))
                message_id = getattr(outcome, "message_id", None) if outcome is not None else None
                if message_id is None and isinstance(outcome, dict):
                    message_id = outcome.get("message_id")
                if message_id is not None:
                    chat_id = getattr(outcome, "chat_id", None) if outcome is not None else None
                    if chat_id is None and isinstance(outcome, dict):
                        chat_id = outcome.get("chat_id")
                    store = load_feedback(production_entrypoint.FEEDBACK_PATH)
                    meta = outcome.as_dict() if hasattr(outcome, "as_dict") else {"message_id": message_id, "chat_id": chat_id}
                    register_post(store, meta, {**item, "content_type": "education", "publication_identity": f"education:{int(item.get('education_id', 0) or 0)}"})
                    save_feedback(store, production_entrypoint.FEEDBACK_PATH)
                    commit_education_lesson(int(item["education_id"]))
                    cadence["last_education_run"] = run_number
                    print(f"[Education Publication] deterministic fallback confirmed lesson={item['education_id']} message_id={message_id}", flush=True)
                    ok = True
        except Exception as exc:
            print(f"[Education Recovery] deterministic fallback failed: {exc!r}", flush=True)
            traceback.print_exc()
    if not ok:
        print(f"[Education Recovery] FAILED slot={slot}; Education remains due", flush=True)
        return 1
    cadence = production_entrypoint._load_cadence()
    cadence["last_education_slot"] = slot or cadence.get("last_education_slot", "")
    cadence["last_education_run"] = run_number
    production_entrypoint._save_cadence(cadence)
    print(f"[Education Published] CONFIRMED lesson_slot={slot} run={run_number} telegram_delivery=successful", flush=True)
    print(f"[Education Recovery] CONFIRMED slot={slot} run={run_number} publication_attempt=successful", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
