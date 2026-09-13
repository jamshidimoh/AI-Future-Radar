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


replace_function("main.py", "_annotate_named_leader_interviews", r'''def _annotate_named_leader_interviews(items, leader_people, leader_priorities=None):
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
    print(f"[Leader Identity Recovery] verified_interviews={matched} | activity_protected={protected} | watchlist_candidates={watch_candidates}")
    return items''')

replace_function("main.py", "_is_protected_leader_interview", r'''def _is_protected_leader_interview(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    if not leader or not (item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("_named_leader_interview")):
        return False
    return has_interview_evidence(item)''')

replace_function("main.py", "_is_protected_leader_activity", r'''def _is_protected_leader_activity(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    return bool(leader and (item.get("is_leader_watch") or item.get("leader_watch_protected")) and _leader_activity_signal(item))''')

replace_function("main.py", "_split_protected", r'''def _split_protected(items, max_protected=2):
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
    candidates.sort(
        key=lambda x: (
            int(x.get("leader_priority", 0) or 0),
            int(x.get("leader_source_authority", _leader_source_authority(x)) or 0),
            1 if _is_protected_leader_interview(x) else 0,
            0 if str(x.get("content_type") or "").lower() == "product_news" else 1,
            float(x.get("editorial_score", 0) or 0),
            str(x.get("published", "")),
        ),
        reverse=True,
    )
    selected = candidates[:max(0, int(max_protected))]
    regular.extend(candidates[len(selected):])
    return selected, regular''')

replace_function("main.py", "_summarize_selected", r'''def _summarize_selected(items, summarize_fn):
    workers = max(1, int(os.getenv("RADAR_SUMMARY_WORKERS", "1") or 1))
    if workers == 1 or len(items) <= 1:
        return [summarize_fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as executor:
        return list(executor.map(summarize_fn, items))''')

replace_function("main.py", "_refill_after_late_dedup", r'''def _refill_after_late_dedup(selected, editorial_pool, select_editorial_fn, max_posts, max_per_source, max_per_type, policy, seen_hashes, runtime_selection_cap=None, *, cap=None):
    if runtime_selection_cap is None:
        runtime_selection_cap = cap if cap is not None else max_posts + int(policy.get("leader_protected_max", 2) or 2)
    target = min(runtime_selection_cap, max_posts + int(policy.get("leader_protected_max", 2) or 2))
    selected = filter_new_items(selected, seen_hashes)
    existing = {str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) for x in selected}
    pool = [
        x for x in editorial_pool
        if not x.get("protected_content")
        and not x.get("protected_slot")
        and str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) not in existing
    ]
    pool = filter_new_items(pool, seen_hashes)
    while len(selected) < target and pool:
        extra = select_editorial_fn(
            pool,
            max_posts=1,
            max_per_source=max_per_source,
            max_per_type=max_per_type,
            policy=policy,
        )
        if not extra:
            break
        candidate = extra[0]
        selected.append(candidate)
        identity = str(candidate.get("canonical_url") or candidate.get("link") or candidate.get("url") or candidate.get("title") or id(candidate))
        pool = [x for x in pool if str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) != identity]
    return unique_candidates(selected)''')

replace_function("main.py", "_mission_coverage_recovery", r'''def _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes):
    mission_areas = {"mind", "future", "mind_cognition", "future_governance"}

    def _area(item):
        return str(item.get("mission_area") or item.get("category") or "").strip().casefold()

    target = 1 if any(_area(x) in mission_areas for x in editorial_pool) else 0
    if target <= 0:
        print("[Mission Coverage Recovery] prepared_publishable=0 score_floor=60.0", flush=True)
        return []
    prepared = sum(
        1
        for x in selected
        if _area(x) in mission_areas
        and float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0) >= NORMAL_SCORE_FLOOR
        and not x.get("_publication_blocked")
    )
    if prepared >= target:
        print(f"[Mission Coverage Recovery] prepared_publishable={prepared} score_floor={NORMAL_SCORE_FLOOR}", flush=True)
        return []
    selected_ids = {str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) for x in selected}
    pool = [
        x for x in editorial_pool
        if not x.get("_publication_blocked")
        and str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) not in selected_ids
    ]
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
            recovered.append((candidate, summary))
            print(f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} title={str(candidate.get('title',''))[:120]} status=recovered", flush=True)
        else:
            print(f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} title={str(candidate.get('title',''))[:120]} status=failed", flush=True)
    print(f"[Mission Coverage Recovery] target={target} prepared={prepared} attempts={attempts} recovered={len(recovered)} status={'ok' if prepared + len(recovered) >= target else 'unmet'}", flush=True)
    return recovered''')

p = ROOT / "src/story_identity.py"
s = p.read_text(encoding="utf-8")
s = s.replace(
'''def _is_same_story_cached(
    candidate: dict[str, Any],
    candidate_url: str,
    candidate_features: dict[str, Any],
    candidate_signature: dict[str, Any],
    prior: tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None],
) -> bool:
    comparable, prior_url, prior_features, prior_signature = prior
    if candidate_url and prior_url and candidate_url == prior_url:
        return True
    kind, _, _ = compare_event_features(candidate_features, prior_features)
    if kind == "DUPLICATE":
        return True
''',
'''def _is_same_story_cached(
    candidate: dict[str, Any],
    candidate_url: str,
    candidate_features: dict[str, Any],
    candidate_signature: dict[str, Any],
    prior: tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None],
    allow_protected_event_match: bool = True,
) -> bool:
    comparable, prior_url, prior_features, prior_signature = prior
    if candidate_url and prior_url and candidate_url == prior_url:
        return True
    if _is_protected_leader(candidate) or _is_protected_leader(comparable):
        candidate_title = " ".join(str(candidate.get("title") or "").casefold().split())
        prior_title = " ".join(str(comparable.get("title") or "").casefold().split())
        if candidate_title and prior_title and candidate_title == prior_title:
            return True
        if not allow_protected_event_match:
            return False
    kind, _, _ = compare_event_features(candidate_features, prior_features)
    if kind == "DUPLICATE":
        return True
''',
1,
)
s = s.replace(
'''def _is_story_duplicate_cached(
    candidate: dict[str, Any],
    cache: list[tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None]],
) -> bool:''',
'''def _is_story_duplicate_cached(
    candidate: dict[str, Any],
    cache: list[tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None]],
    allow_protected_event_match: bool = True,
) -> bool:''',
1,
)
s = s.replace(
'''        _is_same_story_cached(candidate, candidate_url, candidate_features, candidate_signature, prior)
        for prior in cache''',
'''        _is_same_story_cached(candidate, candidate_url, candidate_features, candidate_signature, prior, allow_protected_event_match)
        for prior in cache''',
1,
)
s = s.replace('        if _is_story_duplicate_cached(item, history_cache):', '        if _is_story_duplicate_cached(item, history_cache, allow_protected_event_match=False):', 1)
s = s.replace('        if _is_story_duplicate_cached(item, accepted_cache):', '        if _is_story_duplicate_cached(item, accepted_cache, allow_protected_event_match=True):', 1)
p.write_text(s, encoding="utf-8")

for path in (ROOT / "main.py", ROOT / "src/story_identity.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("RUNTIME_CONTRACT_REPAIR_APPLIED")
