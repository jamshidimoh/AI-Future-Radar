import re
from pathlib import Path


def patch(path, pattern, replacement, count=1, flags=re.S):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    ns, n = re.subn(pattern, replacement, s, count=count, flags=flags)
    if n != count:
        raise SystemExit(f'PATCH_FAILED {path} {n}/{count}: {pattern[:120]}')
    p.write_text(ns, encoding='utf-8')


# Domain 3 import/constants/score routing.
patch('production_entrypoint.py', r'from src\\.protected_editorial_lane import SPECIAL_MAX_PER_PERIOD, choose_additive_candidates\\n', 'from src.protected_editorial_lane import SPECIAL_MAX_PER_PERIOD, choose_additive_candidates\\nfrom src.technical_trend_lane import choose_technical_trend_candidate\\n')
patch('production_entrypoint.py', r'MAX_MIND_IDEAS_VOICES_PER_PERIOD = SPECIAL_MAX_PER_PERIOD\\n', 'MAX_MIND_IDEAS_VOICES_PER_PERIOD = SPECIAL_MAX_PER_PERIOD\\nMAX_TECHNICAL_TREND_PER_PERIOD = 1\\nNORMAL_RELATIVE_SCORE_GAP = 8.0\\n')
patch('production_entrypoint.py', r'def _item_final_score\\(item: dict\\) -> float:\\n    if _is_mind_ideas_voices\\(item\\):', 'def _is_technical_trend(item: dict) -> bool:\\n    return bool(item.get("technical_trend_lane_selected") or item.get("editorial_lane") == "technical_trend")\\n\\n\\ndef _item_final_score(item: dict) -> float:\\n    if _is_technical_trend(item):\\n        try:\\n            return float(item.get("technical_trend_score", 0.0) or 0.0)\\n        except (TypeError, ValueError):\\n            return 0.0\\n    if _is_mind_ideas_voices(item):')

# Normal competitive gate and technical candidate separation.
patch('production_entrypoint.py', r'def _bound_runtime_candidates\\(candidates, max_posts: int, policy: dict\\):\\n    candidates = list\\(candidates or \\[\\]\\)\\n    mind = \\[item for item in candidates if _is_mind_ideas_voices\\(item)\\]\\[:MAX_MIND_IDEAS_VOICES_PER_PERIOD\\]\\n    non_mind = \\[item for item in candidates if not _is_mind_ideas_voices\\(item)\\]\\n', '''def _competitive_normal_candidates(candidates):\\n    candidates = list(candidates or [])\\n    regular = [x for x in candidates if not _is_mind_ideas_voices(x) and not _is_technical_trend(x) and not x.get("_rank_is_tier0")]\\n    protected = [x for x in candidates if x.get("_rank_is_tier0")]\\n    if not regular:\\n        return candidates\\n    scores = [float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0.0) for x in regular]\\n    best = max(scores)\\n    cutoff = max(float(NORMAL_SCORE_FLOOR), best - NORMAL_RELATIVE_SCORE_GAP)\\n    kept = [x for x in regular if float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0.0) >= cutoff]\\n    print(f"[Normal Competitive Gate] candidates={len(regular)} best={best:.2f} cutoff={cutoff:.2f} gap={NORMAL_RELATIVE_SCORE_GAP:.1f} kept={len(kept)} dropped={len(regular)-len(kept)}", flush=True)\\n    return protected + kept\\n\\n\\ndef _bound_runtime_candidates(candidates, max_posts: int, policy: dict):\\n    candidates = list(candidates or [])\\n    mind = [item for item in candidates if _is_mind_ideas_voices(item)][:MAX_MIND_IDEAS_VOICES_PER_PERIOD]\\n    technical = [item for item in candidates if _is_technical_trend(item)][:MAX_TECHNICAL_TREND_PER_PERIOD]\\n    non_mind = [item for item in candidates if not _is_mind_ideas_voices(item) and not _is_technical_trend(item)]\\n''')
patch('production_entrypoint.py', r'for item in protected \\+ normals \\+ mind:', 'for item in protected + normals + technical + mind:', flags=0)
patch('production_entrypoint.py', r'normal=\\{len\\(normals\\)\\} protected=\\{len\\(protected\\)\\} mind_ideas_voices=\\{len\\(mind\\)\\} output=\\{len\\(bounded\\)\\}', 'normal={len(normals)} protected={len(protected)} technical_trend={len(technical)} mind_ideas_voices={len(mind)} output={len(bounded)}', flags=0)

# Interview/podcast recall in Mind, without changing Mind score or cap.
patch('src/protected_editorial_lane.py', r'INTERVIEW_TYPES = \\{\\n    "interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a",\\n\\}\\n', 'INTERVIEW_TYPES = {\\n    "interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a",\\n}\\nINTERVIEW_SIGNAL_TERMS = (r"\\binterview\\b", r"\\bpodcast\\b", r"\\bconversation\\b", r"\\bfireside\\b", r"\\bq&a\\b", r"\\bdiscussion\\b", r"\\bguest\\b", r"\\bepisode\\b")\\n')
patch('src/protected_editorial_lane.py', r'def _thematic_signal\\(item: dict\\[str, Any\\]\\) -> bool:\\n    return any\\(re.search\\(pattern, _text\\(item\\)\\) for pattern in SPECIAL_SIGNAL_PATTERNS\\)\\n\\n\\ndef is_mind_ideas_voices_candidate', 'def _thematic_signal(item: dict[str, Any]) -> bool:\\n    return any(re.search(pattern, _text(item)) for pattern in SPECIAL_SIGNAL_PATTERNS)\\n\\n\\ndef _interview_signal(item: dict[str, Any]) -> bool:\\n    content_type = str(item.get("content_type") or "").strip().casefold()\\n    source_type = str(item.get("source_type") or item.get("type") or item.get("format") or "").strip().casefold()\\n    text = _text(item)\\n    return content_type in INTERVIEW_TYPES or source_type in INTERVIEW_TYPES or any(re.search(pattern, text) for pattern in INTERVIEW_SIGNAL_TERMS)\\n\\n\\ndef is_mind_ideas_voices_candidate')
patch('src/protected_editorial_lane.py', r'    content_type = str\\(item.get\\("content_type"\\) or ""\\)\\.strip\\(\\)\\.casefold\\(\\)\\n    if mission == "mind_cognition" or thematic:\\n        return True\\n    if content_type in INTERVIEW_TYPES and \\(registry_person or explicit_person or mission in MISSION_AREAS\\):\\n', '    content_type = str(item.get("content_type") or "").strip().casefold()\\n    interview = _interview_signal(item)\\n    if mission == "mind_cognition" or thematic:\\n        return True\\n    if interview and (registry_person or explicit_person or mission in MISSION_AREAS or thematic):\\n')

# Provider failures must remain candidate-local.
patch('main.py', r'except \\(QuotaExceeded, TimeoutError, requests\\.exceptions\\.RequestException\\) as exc:', 'except (QuotaExceeded, TimeoutError, ValueError, requests.exceptions.RequestException) as exc:', flags=0)

print('EDITORIAL_LANES_MIGRATION_PATCHED')
