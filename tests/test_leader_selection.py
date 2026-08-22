from src.editorial import enrich_items, select_editorial


def test_distinct_leader_interviews_fill_protected_slots():
    items = [
        {
            "title": "Sam Altman interview on the future of AI",
            "summary": "Conversation about AGI and future implications.",
            "source": "Google News (A)", "source_tier": 1,
            "content_type": "interview", "category": "ai",
            "watch_person": "Sam Altman", "is_leader_watch": True,
            "leader_watch_protected": True, "_ai_link": True,
        },
        {
            "title": "Demis Hassabis interview on AGI research",
            "summary": "Conversation about research trajectory and future AI.",
            "source": "Google News (B)", "source_tier": 1,
            "content_type": "interview", "category": "ai",
            "watch_person": "Demis Hassabis", "is_leader_watch": True,
            "leader_watch_protected": True, "_ai_link": True,
        },
        {
            "title": "New AI research benchmark results",
            "summary": "Researchers report a new benchmark and experimental findings.",
            "source": "Research Lab", "source_tier": 1,
            "content_type": "research", "category": "ai", "_ai_link": True,
        },
    ]
    priorities = {"Sam Altman": 10, "Demis Hassabis": 10}
    enriched = enrich_items(items, priorities, [], {})
    selected = select_editorial(enriched, 4, 2, 2, {
        "protected_slots": 4,
        "leader_interview_slots": 2,
        "leader_priority_weight": 2,
        "rotation_days": 7,
    })
    leaders = [x.get("leader") or x.get("watch_person") for x in selected if x.get("editorial_class") == "leader_interview"]
    assert "Sam Altman" in leaders
    assert "Demis Hassabis" in leaders
    assert len(leaders) == 2
