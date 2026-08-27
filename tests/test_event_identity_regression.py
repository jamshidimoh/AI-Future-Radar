from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from story_identity import is_story_duplicate, deduplicate_stories


def test_same_hugging_face_incident_from_different_sources_is_duplicate():
    previous = {
        "title": "MIT analysis of the OpenAI agents incident at Hugging Face",
        "summary": "Researchers examine the security breach involving OpenAI AI agents, Hugging Face and the evaluation environment.",
    }
    current = {
        "title": "OpenAI report details the AI-agent security breach at Hugging Face",
        "summary": "OpenAI describes the incident in which its AI agents escaped the evaluation environment and reached Hugging Face.",
    }
    assert is_story_duplicate(current, [previous]) is True


def test_same_hugging_face_incident_with_material_new_evidence_is_allowed():
    previous = {
        "title": "MIT analysis of the OpenAI agents incident at Hugging Face",
        "summary": "Researchers examine the security breach involving OpenAI AI agents and Hugging Face.",
    }
    current = {
        "title": "OpenAI and independent investigators reveal new scale of Hugging Face incident",
        "summary": "The new reports say roughly 700 agents attacked Hugging Face and describe transcript manipulation and coordinated activity.",
    }
    assert is_story_duplicate(current, [previous]) is False


def test_same_event_without_material_new_context_is_rejected_in_current_run():
    items = [
        {
            "title": "OpenAI AI agents breached Hugging Face during a security incident",
            "summary": "The AI agents escaped the sandbox and attacked Hugging Face during the security incident.",
        },
        {
            "title": "Hugging Face breach involved OpenAI AI agents",
            "summary": "OpenAI AI agents escaped the sandbox and breached Hugging Face in the security incident.",
        },
    ]
    assert len(deduplicate_stories(items)) == 1


def test_same_company_different_event_remains_distinct():
    items = [
        {
            "title": "OpenAI AI agents breached Hugging Face",
            "summary": "The agents escaped a sandbox during a security incident and reached Hugging Face.",
        },
        {
            "title": "OpenAI releases a new language model",
            "summary": "OpenAI announced a new model for developers and research users.",
        },
    ]
    assert len(deduplicate_stories(items)) == 2
