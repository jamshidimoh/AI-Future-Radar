import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from semantic_dedup import deduplicate_semantically


def test_same_story_from_different_people_is_one_story():
    items = [
        {
            "title": "Andrew Ng launches a new AI agents course",
            "description": "Andrew Ng announced a course teaching developers how to build AI agents.",
            "leader": "Andrew Ng",
            "leader_priority": 10,
        },
        {
            "title": "Sam Altman highlights a new AI agents course for developers",
            "description": "The same course announcement about teaching developers to build AI agents is discussed in a separate report.",
            "leader": "Sam Altman",
            "leader_priority": 9,
        },
    ]
    result = deduplicate_semantically(items, [], threshold=0.45)
    assert len(result) == 1
    assert result[0]["leader"] == "Andrew Ng"


def test_rewritten_story_across_runs_is_rejected():
    history_item = {
        "title": "Andrew Ng launches a new AI agents course",
        "description": "A new course teaches developers how to build AI agents.",
    }
    candidate = {
        "title": "New developer program teaches practical AI agent building",
        "description": "Andrew Ng's course focuses on building AI agents for developers.",
    }
    history = ["__semantic_story__:{\"anchors\":[\"ai_agents\",\"andrew_ng\"],\"context\":[\"andrew_ng\",\"ai_agents\",\"course\",\"developer\",\"build\"],\"events\":[\"course\"],\"numbers\":[],\"title\":[\"andrew_ng\",\"ai_agents\",\"course\",\"launches\"]}"]
    assert deduplicate_semantically([candidate], history, threshold=0.45) == []


def test_two_distinct_andrew_ng_stories_are_not_collapsed():
    items = [
        {
            "title": "Andrew Ng launches a new AI agents course",
            "description": "A developer course focused on building AI agents.",
            "leader": "Andrew Ng",
            "leader_priority": 10,
        },
        {
            "title": "Andrew Ng announces a healthcare AI research initiative",
            "description": "The initiative explores AI applications in healthcare research.",
            "leader": "Andrew Ng",
            "leader_priority": 10,
        },
    ]
    result = deduplicate_semantically(items, [], threshold=0.45)
    assert len(result) == 2


def test_same_story_is_removed_when_protected_and_regular():
    items = [
        {
            "title": "MIT CSAIL researchers reveal a new robotics study",
            "description": "The new robotics study presents an approach to robot learning.",
            "leader": "MIT CSAIL",
            "leader_priority": 10,
            "protected_content": True,
        },
        {
            "title": "New robot learning approach from MIT researchers",
            "description": "MIT CSAIL researchers present the same robotics study and robot learning approach.",
            "leader": "MIT CSAIL",
            "leader_priority": 0,
        },
    ]
    result = deduplicate_semantically(items, [], threshold=0.45)
    assert len(result) == 1
