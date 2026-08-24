from protected_story_identity import probable_same_story


def test_reframed_same_leader_story_is_identified():
    old = {
        "title": "Dario Amodei discusses AI safety and frontier risk",
        "leader": "Dario Amodei",
    }
    new = {
        "title": "Frontier AI safety: Dario Amodei on model risk and safeguards",
        "leader": "Dario Amodei",
    }
    assert probable_same_story(new, old)


def test_new_story_by_same_leader_is_not_identified_as_same_story():
    old = {
        "title": "Dario Amodei discusses AI safety and frontier risk",
        "leader": "Dario Amodei",
    }
    new = {
        "title": "Dario Amodei on scientific discovery and autonomous research",
        "leader": "Dario Amodei",
    }
    assert not probable_same_story(new, old)
