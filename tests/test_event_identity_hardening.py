from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from story_identity import _event_tokens, _material_update_tokens, is_story_duplicate, deduplicate_stories


def test_agent_alias_does_not_recursively_expand():
    sig = {"context": {"ai_agents", "hugging_face", "security_incident"}, "title_text": "AI agents breached Hugging Face"}
    assert _event_tokens(sig) == {"ai_agents", "hugging_face", "security_incident"}


def test_persian_material_update_markers_are_detected():
    sig = {"context": {"hugging_face", "security_incident"}, "title_text": "یافته‌های جدید و شواهد مستقل درباره دامنه حمله"}
    markers = _material_update_tokens(sig)
    assert {"یافته‌ها", "شواهد", "مستقل", "دامنه"}.issubset(markers)


def test_same_event_material_update_survives_as_update():
    previous = {
        "title": "OpenAI AI agents breached Hugging Face",
        "summary": "The agents escaped the sandbox during a security incident at Hugging Face.",
    }
    current = {
        "title": "Independent investigators reveal new Hugging Face incident findings",
        "summary": "New evidence confirms the scale and coordinated behavior of the security incident involving OpenAI AI agents.",
    }
    assert is_story_duplicate(current, [previous]) is False


def test_same_event_without_new_evidence_is_duplicate():
    items = [
        {"title": "OpenAI AI agents breached Hugging Face", "summary": "The agents escaped the sandbox during a security incident."},
        {"title": "Hugging Face security incident involved OpenAI AI agents", "summary": "The agents escaped the sandbox during the same incident."},
    ]
    assert len(deduplicate_stories(items)) == 1

# Keep the regression suite intentionally small and deterministic.
