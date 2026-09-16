import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "production_entrypoint.py"


def replace_once(pattern: str, replacement: str) -> None:
    text = TARGET.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"PATCH_FAILED {count}/1: {pattern[:160]}")
    TARGET.write_text(updated, encoding="utf-8")


replace_once(
    r'"mind_ideas_voices_delivered_count": 0, "tier0_news_delivered_count": 0,',
    '"mind_ideas_voices_delivered_count": 0, "technical_trend_delivered_count": 0, "tier0_news_delivered_count": 0,',
)

replace_once(
    r'''        result = original_summarize\(item\)\n        if result:\n            item\.update\(result\)\n            if _is_mind_ideas_voices\(item\):\n                item\["final_editorial_score"\] = float\(item\.get\("mind_editorial_score", 0\) or 0\)\n                lane = "mind_ideas_voices"\n            else:\n                item\["final_editorial_score"\] = _item_final_score\(item\)\n                lane = "strategic_analytical" if _is_strategic_analytical_signal\(item\) else "normal"''',
    '''        result = original_summarize(item)\n        if result:\n            item.update(result)\n            if _is_technical_trend(item):\n                item["final_editorial_score"] = float(item.get("technical_trend_score", 0) or 0)\n                lane = "technical_trend"\n            elif _is_mind_ideas_voices(item):\n                item["final_editorial_score"] = float(item.get("mind_editorial_score", 0) or 0)\n                lane = "mind_ideas_voices"\n            else:\n                item["final_editorial_score"] = _item_final_score(item)\n                lane = "strategic_analytical" if _is_strategic_analytical_signal(item) else "normal"''',
)

replace_once(
    r'''                is_mind = _is_mind_ideas_voices\(item\)\n                is_tier0 = _is_tier0_publication_candidate\(item\)\n                is_strategic = _is_strategic_analytical_signal\(item\)\n                if not is_mind and not is_tier0:\n                    cadence\["last_published_normal_news_score"\] = score\n                if is_mind:\n                    render_state\["mind_ideas_voices_delivered_count"\] \+= 1\n                elif is_tier0:\n                    render_state\["tier0_news_delivered_count"\] \+= 1\n                else:\n                    render_state\["normal_news_delivered_count"\] \+= 1\n                if is_strategic:\n                    render_state\["strategic_analytical_news_delivered_count"\] \+= 1\n                lane = "mind_ideas_voices" if is_mind else \("tier0" if is_tier0 else "normal"\)''',
    '''                is_mind = _is_mind_ideas_voices(item)\n                is_technical = _is_technical_trend(item)\n                is_tier0 = _is_tier0_publication_candidate(item)\n                is_strategic = _is_strategic_analytical_signal(item)\n                if not is_mind and not is_technical and not is_tier0:\n                    cadence["last_published_normal_news_score"] = score\n                if is_mind:\n                    render_state["mind_ideas_voices_delivered_count"] += 1\n                elif is_technical:\n                    render_state["technical_trend_delivered_count"] += 1\n                elif is_tier0:\n                    render_state["tier0_news_delivered_count"] += 1\n                else:\n                    render_state["normal_news_delivered_count"] += 1\n                if is_strategic:\n                    render_state["strategic_analytical_news_delivered_count"] += 1\n                lane = "mind_ideas_voices" if is_mind else ("technical_trend" if is_technical else ("tier0" if is_tier0 else "normal"))''',
)

replace_once(
    r'''        is_mind = _is_mind_ideas_voices\(story\)\n        priority_person = _is_tier0_publication_candidate\(story\)\n        strategic_analytical = _is_strategic_analytical_signal\(story\)\n        if is_mind:''',
    '''        is_mind = _is_mind_ideas_voices(story)\n        is_technical = _is_technical_trend(story)\n        priority_person = _is_tier0_publication_candidate(story)\n        strategic_analytical = _is_strategic_analytical_signal(story)\n        if is_mind:''',
)

replace_once(
    r'''\[Publication Policy\] PUBLISH mind_ideas_voices mind_rank=\{story\.get\('mind_period_rank'\)\} score=\{score\} normal_floor=not_applied normal_rank=None independent_lane=true", flush=True\)\n            return delivered\(\{"message_id": None\}\)\n        if strategic_analytical''',
    '''[Publication Policy] PUBLISH mind_ideas_voices mind_rank={story.get('mind_period_rank')} score={score} normal_floor=not_applied normal_rank=None independent_lane=true", flush=True)\n            return delivered({"message_id": None})\n        if is_technical:\n            if render_state["technical_trend_delivered_count"] >= MAX_TECHNICAL_TREND_PER_PERIOD:\n                return policy_blocked("technical_trend_quota_exhausted")\n            if not _news_language_ok(story):\n                return policy_blocked("news_language_gate")\n            score = _item_final_score(story)\n            print(f"[Publication Policy] PUBLISH technical_trend tech_rank={story.get('technical_trend_period_rank')} score={score} normal_floor=not_applied normal_rank=None independent_lane=true", flush=True)\n            return delivered({"message_id": None})\n        if strategic_analytical''',
)

replace_once(
    r'''\[Production Contract\] normal_news=\{render_state\['normal_news_delivered_count'\]\} normal_max=\{MAX_NORMAL_NEWS_PER_PERIOD\} mind_ideas_voices=\{render_state\['mind_ideas_voices_delivered_count'\]\} mind_max=\{MAX_MIND_IDEAS_VOICES_PER_PERIOD\} tier0_news=''',
    '''[Production Contract] normal_news={render_state['normal_news_delivered_count']} normal_max={MAX_NORMAL_NEWS_PER_PERIOD} technical_trend={render_state['technical_trend_delivered_count']} technical_max={MAX_TECHNICAL_TREND_PER_PERIOD} mind_ideas_voices={render_state['mind_ideas_voices_delivered_count']} mind_max={MAX_MIND_IDEAS_VOICES_PER_PERIOD} tier0_news=''',
)

print("TECHNICAL_LANE_ISOLATION_PATCHED")
