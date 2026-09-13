from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_function(path: str, name: str, replacement: str) -> None:
    p = ROOT / path
    source = p.read_text(encoding="utf-8")
    pattern = rf"(?ms)^def {re.escape(name)}\(.*?(?=^def |\Z)"
    updated, count = re.subn(pattern, replacement.rstrip() + "\n\n", source, count=1)
    if count != 1:
        raise RuntimeError(f"FUNCTION_NOT_FOUND:{path}:{name}")
    p.write_text(updated, encoding="utf-8")

replace_function("main.py", "_annotate_named_leader_interviews", '''def _annotate_named_leader_interviews(items, leader_people, leader_priorities=None):
    names = sorted({str(x).strip() for x in (leader_people or []) if str(x).strip()}, key=len, reverse=True)
    priorities = {str(k).strip(): int(v or 0) for k, v in (leader_priorities or {}).items()}
    matched = protected = watch_candidates = 0
    for item in items:
        existing = str(item.get("leader") or item.get("watch_person") or "").strip()
        if existing:
            if existing in names:
                watch_candidates += 1
                item["leader_priority"] = priorities.get(existing, int(item.get("leader_priority", 0) or 0))
                if _direct_interview_signal(item):
                    item["_named_leader_interview"] = True
                    item["is_leader_watch"] = True
                    item["leader_watch_protected"] = True
                    matched += 1
                elif _leader_activity_signal(item):
                    item["leader_activity_signal"] = True
                    item["is_leader_watch"] = True
                    item["leader_watch_protected"] = True
                    protected += 1
            continue
        text = _text(item)
        matched_name = next((name for name in names if _contains_person(text, name)), None)
        if matched_name:
            item["watch_person"] = matched_name
            item["leader"] = matched_name
            item["is_leader"] = True
            item["is_leader_watch"] = True
            item["leader_priority"] = priorities.get(matched_name, 0)
            watch_candidates += 1
            if _direct_interview_signal(item):
                item["_named_leader_interview"] = True
                item["leader_watch_protected"] = True
                matched += 1
            elif _leader_activity_signal(item):
                item["leader_activity_signal"] = True
                item["leader_watch_protected"] = True
                protected += 1
    print(f"[Leader Identity Recovery] verified_interviews={matched} | activity_protected={protected} | watchlist_candidates={watch_candidates}", flush=True)
    return items''')

replace_function("main.py", "_is_protected_leader_interview", '''def _is_protected_leader_interview(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    if not leader or not (item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("_named_leader_interview")):
        return False
    return has_interview_evidence(item)''')

replace_function("main.py", "_is_protected_leader_activity", '''def _is_protected_leader_activity(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    return bool(leader and (item.get("is_leader_watch") or item.get("leader_watch_protected")) and _leader_activity_signal(item))''')

replace_function("main.py", "_split_protected", '''def _split_protected(items, max_protected=2):
    candidates, regular = [], []
    for raw in items:
        item = dict(raw)
        if _is_protected_leader_interview(item) or _is_protected_leader_activity(item):
            item["protected_content"] = True
            item["protected_reason"] = "leader_interview_or_activity"
            item["_ai_link"] = True
            item["leader_watch_protected"] = True
            item["leader_source_authority"] = _leader_source_authority(item)
            candidates.append(item)
        else:
            regular.append(item)
    candidates.sort(key=lambda x: (
        int(x.get("leader_priority", 0) or 0),
        int(x.get("leader_source_authority", _leader_source_authority(x)) or 0),
        1 if _is_protected_leader_interview(x) else 0,
        0 if str(x.get("content_type") or "").lower() == "product_news" else 1,
        float(x.get("editorial_score", 0) or 0),
        str(x.get("published", "")),
    ), reverse=True)
    selected = candidates[:max(0, int(max_protected))]
    for item in selected:
        item["protected_slot"] = True
    regular.extend(candidates[len(selected):])
    return selected, regular''')

replace_function("main.py", "_summarize_selected", '''def _summarize_selected(items, summarize_fn):
    workers = max(1, int(os.getenv("RADAR_SUMMARY_WORKERS", "1") or 1))
    if workers == 1 or len(items) <= 1:
        return [summarize_fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as executor:
        return list(executor.map(summarize_fn, items))''')

replace_function("main.py", "_refill_after_late_dedup", '''def _refill_after_late_dedup(selected, editorial_pool, select_editorial_fn, max_posts, max_per_source, max_per_type, policy, seen_hashes, runtime_selection_cap=None, *, cap=None):
    if runtime_selection_cap is None:
        runtime_selection_cap = cap if cap is not None else max_posts + int(policy.get("leader_protected_max", 2) or 2)
    target = min(runtime_selection_cap, max_posts + int(policy.get("leader_protected_max", 2) or 2))
    selected = filter_new_items(selected, seen_hashes)
    existing = {str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) for x in selected}
    pool = [x for x in editorial_pool if not x.get("protected_content") and not x.get("protected_slot") and str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) not in existing]
    pool = filter_new_items(pool, seen_hashes)
    while len(selected) < target and pool:
        extra = select_editorial_fn(pool, max_posts=1, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy)
        if not extra:
            break
        candidate = extra[0]
        selected.append(candidate)
        identity = str(candidate.get("canonical_url") or candidate.get("link") or candidate.get("url") or candidate.get("title") or id(candidate))
        pool = [x for x in pool if str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) != identity]
    return unique_candidates(selected)''')

replace_function("main.py", "_mission_coverage_recovery", '''def _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes):
    mission_areas = {"mind", "future", "mind_cognition", "future_governance"}
    def _area(item):
        return str(item.get("mission_area") or item.get("category") or "").strip().casefold()
    target = 1 if any(_area(x) in mission_areas for x in editorial_pool) else 0
    if target <= 0:
        print("[Mission Coverage Recovery] prepared_publishable=0 score_floor=60.0", flush=True)
        return []
    prepared = sum(1 for x in selected if _area(x) in mission_areas and float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0) >= NORMAL_SCORE_FLOOR and not x.get("_publication_blocked"))
    if prepared >= target:
        print(f"[Mission Coverage Recovery] prepared_publishable={prepared} score_floor={NORMAL_SCORE_FLOOR}", flush=True)
        return []
    selected_ids = {str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) for x in selected}
    pool = [x for x in editorial_pool if not x.get("_publication_blocked") and str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) not in selected_ids]
    recovered, attempts = [], 0
    while prepared + len(recovered) < target and pool and attempts < max(1, int(policy.get("replacement_buffer", 3) or 3)):
        attempts += 1
        chosen = select_editorial_fn(pool, max_posts=1, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy)
        if not chosen:
            break
        candidate = chosen[0]
        identity = str(candidate.get("canonical_url") or candidate.get("link") or candidate.get("url") or candidate.get("title") or id(candidate))
        pool = [x for x in pool if str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) != identity]
        summary = summarize_fn(candidate)
        if summary:
            candidate.update(summary)
            candidate["_mission_recovery"] = True
            recovered.append((candidate, summary))
            print(f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} title={str(candidate.get('title',''))[:120]} status=recovered", flush=True)
        else:
            print(f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} title={str(candidate.get('title',''))[:120]} status=failed", flush=True)
    print(f"[Mission Coverage Recovery] target={target} prepared={prepared} attempts={attempts} recovered={len(recovered)} status={'ok' if prepared + len(recovered) >= target else 'unmet'}", flush=True)
    return recovered''')

p = ROOT / "src/story_identity.py"
s = p.read_text(encoding="utf-8")
if "from protected_story_identity import probable_same_story" not in s:
    s = s.replace("from semantic_dedup import get_story_signature, _similarity\n", "from semantic_dedup import get_story_signature, _similarity\nfrom protected_story_identity import probable_same_story\n")
# Current-run protected candidates: reject strong title/body rewrites, but never use this broader rule against history.
needle = '''        if not allow_protected_event_match:\n            return False\n        if probable_same_story(candidate, comparable):\n            return True\n'''
if needle not in s:
    needle = '''        if not allow_protected_event_match:\n            return False\n'''
    replacement = '''        if not allow_protected_event_match:\n            return False\n        if probable_same_story(candidate, comparable):\n            return True\n'''
    s = s.replace(needle, replacement, 1)
# Preserve strict history semantics: no broad protected-story matching when checking persisted history.
p.write_text(s, encoding="utf-8")

run_workflow = ROOT / ".github" / "workflows" / "run.yml"
run_text = run_workflow.read_text(encoding="utf-8")
if "Tehran publication windows:" not in run_text:
    run_workflow.write_text("# Tehran publication windows: cron entries below are expressed in UTC.\n" + run_text, encoding="utf-8")

for path in (ROOT / "main.py", ROOT / "src/story_identity.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
