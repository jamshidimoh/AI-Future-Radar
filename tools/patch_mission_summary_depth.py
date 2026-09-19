from pathlib import Path

path = Path('src/summarize.py')
text = path.read_text(encoding='utf-8')
old_import = 'from src.llm_router_light import call_llm_with_fallback, get_quality_chain\n'
new_import = old_import + 'from src.unified_editorial_selection import mission_area\n'
if old_import not in text or 'from src.unified_editorial_selection import mission_area' in text:
    raise SystemExit('unexpected import state')
text = text.replace(old_import, new_import, 1)
old = '''def summarize_item(item):
    category = item.get("category", "ai")
    prompt = _PROMPT.format(depth=_DEPTH.get(category, _DEPTH["ai"]))
    raw_text = _source_text(item)
    user = (
        f"عنوان: {item.get('title','')}\\n"
        f"منبع: {item.get('source','')}\\n"
        f"نوع: {item.get('content_type','news')}\\n"
        f"شخص کلیدی: {item.get('leader') or item.get('watch_person') or ''}\\n"
        f"متن: {raw_text[:3500]}"
    )
'''
new = '''def summarize_item(item):
    category = item.get("category", "ai")
    area = mission_area(item)
    depth_key = {
        "ai_core": "ai",
        "convergence": "quantum",
        "mind_cognition": "mind",
        "future_governance": "future",
    }.get(area, category if category in _DEPTH else "ai")
    prompt = _PROMPT.format(depth=_DEPTH.get(depth_key, _DEPTH["ai"]))
    raw_text = _source_text(item)
    user = (
        f"عنوان: {item.get('title','')}\\n"
        f"منبع: {item.get('source','')}\\n"
        f"نوع: {item.get('content_type','news')}\\n"
        f"حوزه مأموریت: {area}\\n"
        f"شخص کلیدی: {item.get('leader') or item.get('watch_person') or ''}\\n"
        f"متن: {raw_text[:3500]}"
    )
'''
if old not in text:
    raise SystemExit('summarize_item target not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
