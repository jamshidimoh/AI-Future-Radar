def _publication_summary_budget(items, max_posts, policy):
    buffer = max(0, int(policy.get("replacement_buffer", 3) or 3))
    mind = [x for x in items if _is_mind_ideas_voices(x)][:MAX_MIND_IDEAS_VOICES_PER_PERIOD]
    mind_ids = {id(x) for x in mind}
    protected = [
        x for x in items
        if (x.get("protected_slot") or x.get("protected_content"))
        and id(x) not in mind_ids
    ]
    normal = [x for x in items if id(x) not in mind_ids and x not in protected]
    eligible_protected = [x for x in protected if float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0) >= PROTECTED_SUMMARY_SCORE_FLOOR]
    normal_window = max_posts + buffer
    bounded = eligible_protected[:max_posts] + normal[:normal_window] + mind
    print(f"[Publication Summary Budget] input={len(items)} protected={len(eligible_protected)} mind_ideas_voices={len(mind)} normal_window={normal_window} output={len(bounded)} normal_limit={normal_window} mind_limit={MAX_MIND_IDEAS_VOICES_PER_PERIOD} replacement_buffer={buffer} normal_score_floor={NORMAL_SCORE_FLOOR} mind_score_floor=not_applied", flush=True)
    return bounded


def _refill_after_late_dedup(selected, editorial_pool, select_editorial_fn, max_posts, max_per_source, max_per_type, policy, seen_hashes, runtime_selection_cap=None, *, cap=None):
    if runtime_selection_cap is None:
        runtime_selection_cap = cap if cap is not None else max_posts + int(policy.get("leader_protected_max", 2) or 2) + MAX_MIND_IDEAS_VOICES_PER_PERIOD
    target = min(runtime_selection_cap, max_posts + int(policy.get("leader_protected_max", 2) or 2) + MAX_MIND_IDEAS_VOICES_PER_PERIOD)
    selected = filter_new_items(selected, seen_hashes)
    existing = {_publication_identity(x) for x in selected}
    pool = [x for x in editorial_pool if not x.get("protected_content") and not x.get("protected_slot") and _publication_identity(x) not in existing]
    pool = filter_new_items(pool, seen_hashes)
    while len(selected) < target and pool:
        extra = select_editorial_fn(pool, max_posts=1, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy)
        if not extra: