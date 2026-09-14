"""Explicit paradigm/tension map for comparative analysis."""

from typing import Any, cast

TENSIONS = [
    {
        "id": "llm_vs_world_models",
        "label": "Connectionism vs world models/causality",
        "sides": ["connectionist_scaling", "world_models_causality"],
        "people": {"connectionist_scaling": ["Sam Altman", "Ilya Sutskever"],
                   "world_models_causality": ["Yann LeCun"]},
        "questions": ["What representation is sufficient for robust intelligence?", "Is scaling enough for causal/world understanding?"]
    },
    {
        "id": "silicon_vs_biology",
        "label": "Silicon computation vs biological/embodied intelligence",
        "sides": ["silicon", "bio_embodied"],
        "people": {"silicon": ["Jensen Huang", "Sam Altman"],
                   "bio_embodied": ["Michael Levin", "Karl Friston"]},
        "questions": ["Does intelligence require biological embodiment?", "Can alternative substrates produce useful intelligence?"]
    },
    {
        "id": "ai_consciousness",
        "label": "Behavioral evidence vs phenomenal consciousness",
        "sides": ["functional_behavior", "phenomenology"],
        "people": {"functional_behavior": ["Daniel Dennett", "Michael Graziano"],
                   "phenomenology": ["David Chalmers", "Anil Seth", "Christof Koch"]},
        "questions": ["What evidence would count as machine consciousness?", "Can function be separated from experience?"]
    },
]


def tension_for_person(person: str) -> list[dict[str, Any]]:
    name = str(person or "").casefold()
    return [t for t in TENSIONS if any(name == p.casefold() for side in cast(dict[str, list[str]], t["people"]).values() for p in side)]


def related_opponents(person: str) -> list[str]:
    out: list[str] = []
    for tension in tension_for_person(person):
        people = cast(dict[str, list[str]], tension["people"])
        for side_people in people.values():
            for p in side_people:
                if p.casefold() != str(person or "").casefold():
                    out.append(p)
    return sorted(set(out))
