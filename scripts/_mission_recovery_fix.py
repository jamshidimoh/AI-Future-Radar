from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
NEW_FUNCTION = '''def _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes):
    """Recover missing mission lanes with a lane-targeted, generic portfolio handoff."""
    def _area(item):
        return str(item.get("mission_area") or item.get("category") or "").strip().casefold()

    mission_targets = []
    try:
        configured = load_yaml(ROOT / "config" / "mission_policy.yaml").get("mission", {}) or {}
        if int(configured.get("convergence_target", 0) or 0) > 0:
            mission_targets.append("convergence")
        if int(configured.get("mind_future_target", 0) or 0) > 0:
            mission_targets.append("mind_cognition")
        if int(configured.get("future_governance_target", 0) or 0) > 0:
            mission_targets.append("future_governance")
    except Exception as exc:
        logger.warning("Mission recovery config load failed; using safe defaults: %s", exc)
        mission_targets = ["convergence", "mind_cognition"]

    def _normalized_target_area(area):
        aliases = {"mind": "mind_cognition", "cognition": "mind_cognition", "future": "future_governance"}
        return aliases.get(str(area).strip().casefold(), str(area).strip().casefold())

    mission_targets = [_normalized_target_area(x) for x in mission_targets]
    pool_by_area = {area: [] for area in mission_targets}
    for item in editorial_pool:
        if item.get("_publication_blocked"):
            continue
        area = _normalized_target_area(_area(item))
        if area in pool_by_area:
            pool_by_area[area].append(item)

    selected_ids = {_publication_identity(x) for x in selected}
    prepared_by_area = {area: 0 for area in mission_targets}
    for item in selected:
        area = _normalized_target_area(_area(item))
        if area in prepared_by_area and float(item.get("final_editorial_score", item.get("editorial_score", 0)) or 0) >= NORMAL_SCORE_FLOOR and not item.get("_publication_blocked"):
            prepared_by_area[area] += 1

    recovered = []
    attempts_limit = max(1, int(policy.get("replacement_buffer", 3) or 3))
    for area in mission_targets:
        if prepared_by_area.get(area, 0) >= 1:
            continue
        lane_pool = [x for x in pool_by_area.get(area, []) if _publication_identity(x) not in selected_ids]
        attempts = 0
        lane_recovered = 0
        while lane_pool and attempts < attempts_limit and lane_recovered < 1:
            attempts += 1
            chosen = select_editorial_fn(lane_pool, max_posts=1, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy)
            if not chosen:
                break
            candidate = chosen[0]
            identity = _publication_identity(candidate)
            lane_pool = [x for x in lane_pool if _publication_identity(x) != identity]
            summary = _safe_summarize(candidate, summarize_fn)
            if summary:
                candidate.update(summary)
                candidate["_mission_recovery"] = True
                candidate["_mission_recovery_area"] = area
                recovered.append((candidate, summary))
                selected_ids.add(identity)
                lane_recovered += 1
                print(f"[Mission Coverage Recovery] attempt={attempts} area={area} title={str(candidate.get('title',''))[:120]} status=recovered", flush=True)
            else:
                print(f"[Mission Coverage Recovery] attempt={attempts} area={area} title={str(candidate.get('title',''))[:120]} status=failed", flush=True)
        status = "ok" if lane_recovered else "unmet"
        print(f"[Mission Coverage Recovery] target=1 prepared={prepared_by_area.get(area, 0)} attempts={attempts} recovered={lane_recovered} area={area} status={status}", flush=True)

    return recovered
'''
text = MAIN.read_text(encoding="utf-8")
start = text.index("def _mission_coverage_recovery(")
end = text.index("\ndef main(", start)
MAIN.write_text(text[:start] + NEW_FUNCTION.rstrip() + text[end:], encoding="utf-8")
print("MISSION_RECOVERY_PATCHED")
