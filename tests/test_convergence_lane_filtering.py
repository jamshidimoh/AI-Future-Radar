from __future__ import annotations

from src.fetch_youtube import _is_low_signal_video
from src.unified_editorial_selection import (
    _keyword_match_area,
    is_mission_relevant,
)


def test_global_forum_video_without_ai_signal_is_low_signal():
    channel = {"name": "World Economic Forum", "type": "global_forum"}
    non_ai_title = "We all depend on the construction industry. Here's why it urgently needs more workers"
    assert _is_low_signal_video(non_ai_title, "", channel) is True

    finance_title = "3 Top Finance Stories & CEO Gender Gap| WEF | Stories of the Week"
    assert _is_low_signal_video(finance_title, "A review of finance and markets", channel) is True

    ai_title = "Jensen Huang on AI Infrastructure and the Next Industrial Revolution"
    assert _is_low_signal_video(ai_title, "Discussion on artificial intelligence and computing", channel) is False


def test_low_signal_finance_roundup_rejected_by_mission_relevance():
    item = {
        "title": "3 Top Finance Stories & CEO Gender Gap| WEF | Stories of the Week",
        "summary": "Weekly roundup of financial markets, gender gap, and economic updates.",
        "category": "ai",
        "mission_area": "convergence",
    }
    assert is_mission_relevant(item) is False


def test_deep_tech_convergence_keywords_match_properly():
    quantum_item = {
        "title": "Breakthrough in quantum computing and silicon spin qubits",
        "summary": "Researchers achieve new coherence times in quantum hardware.",
    }
    assert _keyword_match_area(quantum_item, content_only=True) == "convergence"

    robotics_item = {
        "title": "New humanoid robotics platform for autonomous factory logistics",
        "summary": "The system pairs embodied ai with humanoid mechanics.",
    }
    assert _keyword_match_area(robotics_item, content_only=True) == "convergence"


def test_generic_materials_or_energy_without_deep_tech_does_not_falsely_match_convergence():
    construction_item = {
        "title": "Supply chain issues delay building materials for residential housing",
        "summary": "Contractors report rising costs of concrete, lumber, and other construction materials.",
    }
    assert _keyword_match_area(construction_item, content_only=True) != "convergence"
