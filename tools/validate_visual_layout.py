from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / "digital_transformation_booklet" / "chapter-01"
SOURCE = CHAPTER / "source" / "chapter-01.md"
PDF = CHAPTER / "pdf" / "فصل-01-تحول-دیجیتال-2-0.pdf"
REPORT_DIR = CHAPTER / "reports"
REPORT_JSON = REPORT_DIR / "visual-layout-report.json"

# A4 right content edge for the booklet's 2.5 cm right margin.
RIGHT_MARGIN_PT = 2.5 * 72 / 2.54
RIGHT_TOLERANCE_PT = 8.0
MIN_HEADING_MATCH_RATIO = 0.90


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("ي", "ی").replace("ى", "ی")
    text = text.replace("ك", "ک")
    text = text.replace("ـ", "")
    text = text.replace("\u200c", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*[-:]\s*", " - ", text)
    return text


def source_headings() -> list[dict]:
    headings: list[dict] = []
    for line_no, line in enumerate(SOURCE.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not m:
            continue
        text = normalize(re.sub(r"\*+", "", m.group(2)))
        headings.append({"level": len(m.group(1)), "text": text, "line": line_no})
    return headings


def pdf_lines() -> list[dict]:
    doc = fitz.open(PDF)
    rows: list[dict] = []
    for page_index, page in enumerate(doc):
        data = page.get_text("dict", sort=True)
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans)
                x0 = min(s["bbox"][0] for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                x1 = max(s["bbox"][2] for s in spans)
                y1 = max(s["bbox"][3] for s in spans)
                max_size = max(float(s.get("size", 0)) for s in spans)
                bold = any("Bold" in str(s.get("font", "")) for s in spans)
                rows.append({
                    "page": page_index + 1,
                    "text": normalize(text),
                    "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                    "font_size": round(max_size, 2),
                    "bold": bold,
                })
    doc.close()
    return rows


def match_headings(expected: list[dict], lines: list[dict]) -> list[dict]:
    results: list[dict] = []
    cursor = 0
    for h in expected:
        found = None
        for idx in range(cursor, len(lines)):
            candidate = lines[idx]["text"]
            if candidate == h["text"]:
                found = (idx, lines[idx], "exact")
                break
            # Some renderers split mixed RTL/LTR punctuation. Token equality is a
            # safe second pass because normalization already removed presentation noise.
            if candidate and h["text"] and candidate.split() == h["text"].split():
                found = (idx, lines[idx], "token")
                break
        if found:
            idx, line, method = found
            cursor = idx + 1
            results.append({**h, "status": "matched", "method": method, "pdf": line})
        else:
            results.append({**h, "status": "not_found"})
    return results


def main() -> int:
    if not SOURCE.exists():
        print(f"SOURCE NOT FOUND: {SOURCE}")
        return 1
    if not PDF.exists() or PDF.stat().st_size == 0:
        print(f"PDF NOT FOUND OR EMPTY: {PDF}")
        return 1

    expected = source_headings()
    lines = pdf_lines()
    results = match_headings(expected, lines)

    matched = [r for r in results if r["status"] == "matched"]
    missing = [r for r in results if r["status"] != "matched"]

    # Geometry is evaluated from the reconstructed PDF line bbox, not from a single span.
    aligned = []
    alignment_fail = []
    for r in matched:
        page_width = fitz.paper_rect("a4").width
        expected_right = page_width - RIGHT_MARGIN_PT
        x1 = float(r["pdf"]["bbox"][2])
        gap = expected_right - x1
        item = {"text": r["text"], "page": r["pdf"]["page"], "x1": round(x1, 2), "expected_right": round(expected_right, 2), "gap": round(gap, 2)}
        if abs(gap) <= RIGHT_TOLERANCE_PT:
            aligned.append(item)
        else:
            alignment_fail.append(item)

    ratio = len(matched) / max(1, len(expected))
    result = "PASS" if ratio >= MIN_HEADING_MATCH_RATIO and not alignment_fail else "FAIL"

    payload = {
        "result": result,
        "source": str(SOURCE.relative_to(ROOT)),
        "pdf": str(PDF.relative_to(ROOT)),
        "source_headings": len(expected),
        "pdf_heading_matches": len(matched),
        "right_aligned_matches": len(aligned),
        "right_alignment_failures": len(alignment_fail),
        "match_ratio": round(ratio, 4),
        "right_tolerance_pt": RIGHT_TOLERANCE_PT,
        "missing_headings": [h["text"] for h in missing],
        "alignment_failures": alignment_fail,
        "matched_headings": results,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("# Visual Layout QA")
    print(f"- source_headings: {len(expected)}")
    print(f"- pdf_heading_matches: {len(matched)}")
    print(f"- right_aligned_matches: {len(aligned)}")
    for h in missing:
        print(f"- NOT FOUND: {h['text']}")
    for item in alignment_fail:
        print(f"- FAIL RIGHT: {item['text']}; x1={item['x1']}; expected≈{item['expected_right']}; gap={item['gap']}")
    print(f"\n## Result\n\n{result}")
    print(f"\nReport: {REPORT_JSON}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
