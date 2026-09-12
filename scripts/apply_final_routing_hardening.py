from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_if_present(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise SystemExit(f"{label}: expected source not found")


replace_if_present(
    ROOT / "src/llm_router_light.py",
    'except concurrent.futures.TimeoutError as exc:\n            last_error = TimeoutError(f"{name}: provider timeout")',
    'except concurrent.futures.TimeoutError:\n            last_error = TimeoutError(f"{name}: provider timeout")',
    "llm timeout handler",
)

main_path = ROOT / "main.py"
s = main_path.read_text(encoding="utf-8")
anchor = 'TELEGRAM_SAFE_TEXT_LIMIT = 3900\nPROTECTED_SUMMARY_SCORE_FLOOR = 60.0\n'
if anchor in s and 'NORMAL_SCORE_FLOOR = 60.0' not in s:
    s = s.replace(anchor, anchor + 'NORMAL_SCORE_FLOOR = 60.0\n', 1)
old = '        if item.get("protected_slot"):\n            try: score = float(item.get("final_editorial_score", item.get("editorial_score", 0)) or 0)'
new = '        if item.get("protected_slot") or item.get("protected_content"):\n            try: score = float(item.get("final_editorial_score", item.get("editorial_score", 0)) or 0)'
if old in s:
    s = s.replace(old, new, 1)

if 'Publication Lazy Refill' not in s:
    pattern = re.compile(
        r'    print\("\[7/7\] Telegram publication"\); sent = 0\n'
        r'    for item in selected:.*?'
        r'    save_seen\(seen_hashes, seen_signatures, source_history\); print\(f"Posts sent: \{sent\}/\{len\(selected\)\}"\)',
        re.S,
    )
    replacement = '''    print("[7/7] Telegram publication"); sent = 0
    initial_selected_count = len(selected)
    publication_attempted = set()
    lazy_replacements = 0
    contract = load_editorial_contract()
    replacement_limit = max(0, int(contract.get("replacement_buffer", 0) or 0))
    next_candidate_index = 0

    def _publication_identity(item):
        return str(item.get("canonical_url") or item.get("link") or item.get("url") or item.get("title") or id(item))

    publication_attempted.update(_publication_identity(item) for item in selected)

    def _prepare_lazy_replacement():
        nonlocal lazy_replacements, next_candidate_index
        if lazy_replacements >= replacement_limit:
            return None
        while next_candidate_index < len(editorial_pool):
            candidate = editorial_pool[next_candidate_index]
            next_candidate_index += 1
            identity = _publication_identity(candidate)
            if identity in publication_attempted:
                continue
            candidate_score = float(candidate.get("final_editorial_score", candidate.get("editorial_score", 0)) or 0)
            is_protected = bool(candidate.get("protected_content"))
            if is_protected:
                if candidate_score < PROTECTED_SUMMARY_SCORE_FLOOR:
                    continue
            else:
                normal_rank = candidate.get("normal_period_rank")
                try:
                    normal_rank = int(normal_rank)
                except (TypeError, ValueError):
                    continue
                if normal_rank > int(contract.get("candidate_window", 6)):
                    continue
                if candidate_score < NORMAL_SCORE_FLOOR:
                    continue
            candidate = dict(candidate)
            summary = summarize_fn(candidate)
            if not summary:
                candidate["_publication_blocked"] = True
                print(f"[Publication Lazy Refill] summary blocked; skipping candidate: {str(candidate.get('title',''))[:120]}", flush=True)
                continue
            candidate.update(summary)
            candidate["final_editorial_score"] = float(candidate.get("final_editorial_score", candidate.get("editorial_score", 0)) or 0)
            candidate["source_image"] = resolve_image_fn(candidate)
            publication_attempted.add(identity)
            lazy_replacements += 1
            print(f"[Publication Lazy Refill] prepared replacement={lazy_replacements}/{replacement_limit} normal_rank={candidate.get('normal_period_rank')} score={candidate.get('final_editorial_score')} title={str(candidate.get('title',''))[:120]}", flush=True)
            return candidate
        return None

    for item in selected:
        if item.get("_publication_blocked"):
            continue
        try:
            source_name = str(item.get("source") or item.get("source_name") or "منبع"); link = str(item.get("link") or item.get("url") or ""); post = format_fn(item, source_name, link, is_video=str(item.get("source_type") or "").lower() in {"youtube", "video"}, published=item.get("published", ""), content_type=item.get("content_type", "news"), source_tier=item.get("source_tier", 3), source_type=item.get("source_type", "news"), leader=item.get("leader") or item.get("watch_person") or "")
            if not _publication_text_within_limit(post):
                replacement = _prepare_lazy_replacement()
                if replacement is not None:
                    selected.append(replacement)
                continue
            result = deliver_fn(post, image_url=str(item.get("source_image") or ""), source_link=link)
            if hasattr(result, "status"):
                status = getattr(result, "status"); status_value = getattr(status, "value", str(status))
                if status_value == "delivered":
                    sent += 1; persist_fn(item, seen_hashes, seen_signatures, source_history); continue
                if status_value in {"policy_blocked", "rejected", "duplicate"}:
                    print(f"[Publication Contract] candidate rejected reason={getattr(result, 'reason', '')}; continuing to next ranked candidate", flush=True)
                    replacement = _prepare_lazy_replacement()
                    if replacement is not None:
                        selected.append(replacement)
                    continue
                raise RuntimeError(f"Telegram transport failure: {getattr(result, 'reason', 'unknown')}")
            if not result:
                raise RuntimeError("Telegram delivery returned false")
            sent += 1; persist_fn(item, seen_hashes, seen_signatures, source_history)
        except Exception as exc:
            print(f"[ERROR] Telegram send failed for {item.get('title','')[:100]}: {exc}", flush=True)
    print(f"[Publication Lazy Refill] initial={initial_selected_count} lazy_replacements={lazy_replacements} final_attempt_queue={len(selected)}", flush=True)
    save_seen(seen_hashes, seen_signatures, source_history); print(f"Posts sent: {sent}/{len(selected)}")'''
    m = pattern.search(s)
    if not m:
        raise SystemExit("publication loop: expected block not found")
    s = s[:m.start()] + replacement + s[m.end():]

main_path.write_text(s, encoding="utf-8")

quality_path = ROOT / ".github" / "workflows" / "test-quality.yml"
replace_if_present(
    quality_path,
    "      - name: Ruff changed-surface gate\n        run: python -m ruff check --select F src/llm_router_light.py tests/test_hf_light_router.py",
    "      - name: Ruff changed-surface gate\n        run: python -m ruff check --select F src/llm_router_light.py src/free_model_registry.py src/production_router_policy.py tests/test_llm_health_persistence.py tests/test_nara_router_integration.py",
    "Ruff changed-surface gate",
)

print("FINAL_ROUTING_HARDENING_APPLIED")
