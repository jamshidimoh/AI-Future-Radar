"""Generate non-publishing previews for education pilot lessons 55–57.

This script intentionally does not read or write education_state.json and never
calls Telegram publication code. It is safe to use for isolated editorial QA.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.educational_content import _generate, _lesson_sequence, format_educational_post

PILOT_IDS = (55, 56, 57)
OUTPUT_DIR = Path("artifacts/education_pilot_preview")


def main() -> int:
    lessons = {
        int(lesson.get("id", 0) or 0): lesson
        for _, lesson in _lesson_sequence()
    }
    missing = [lesson_id for lesson_id in PILOT_IDS if lesson_id not in lessons]
    if missing:
        raise SystemExit(f"Pilot lessons missing from active curriculum: {missing}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for lesson_id in PILOT_IDS:
        lesson = lessons[lesson_id]
        generated, sources = _generate(lesson)
        if not generated:
            raise SystemExit(
                f"Lesson {lesson_id} failed source/LLM/editorial generation; "
                "no preview artifact will be treated as accepted."
            )

        organizations = sorted(
            {str(source.get("organization")) for source in sources if source.get("organization")}
        )
        if len(sources) < 2 or len(organizations) < 2:
            raise SystemExit(
                f"Lesson {lesson_id} has insufficient independent verified sources: "
                f"count={len(sources)} organizations={organizations}"
            )

        item = {
            "content_type": "education",
            "category": "ai",
            "education_id": lesson_id,
            "education_total": len(_lesson_sequence()),
            "education_track": "foundation",
            "education_track_label": "مفاهیم پایه و بنیادی",
            "education_number": lesson_id,
            "education_status": lesson.get("status", "established"),
            "education_title": lesson.get("title", ""),
            "education_term_a": lesson["a"]["term"],
            "education_term_a_fa": lesson["a"]["fa"],
            "education_term_b": lesson["b"]["term"],
            "education_term_b_fa": lesson["b"]["fa"],
            "education_sources": sources,
            **generated,
        }
        rendered = format_educational_post(item)
        if not rendered or "\u2067" not in rendered or "\u2069" not in rendered:
            raise SystemExit(f"Lesson {lesson_id} failed Persian RTL rendering checks.")

        output_path = OUTPUT_DIR / f"lesson_{lesson_id:03d}.html.txt"
        output_path.write_text(rendered, encoding="utf-8")
        results.append(
            {
                "lesson_id": lesson_id,
                "title": lesson.get("title"),
                "provider": generated.get("_provider"),
                "review_provider": generated.get("_review_provider"),
                "verified_sources": sources,
                "organizations": organizations,
                "preview_file": output_path.name,
                "rtl_rendering": "passed",
                "state_mutation": False,
                "telegram_publication": False,
            }
        )
        print(
            f"[Education Pilot] lesson={lesson_id} generated; "
            f"sources={len(sources)} organizations={len(organizations)} "
            f"provider={generated.get('_provider')}",
            flush=True,
        )

    summary = {
        "pilot_lessons": list(PILOT_IDS),
        "generated_count": len(results),
        "state_mutation": False,
        "telegram_publication": False,
        "results": results,
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
