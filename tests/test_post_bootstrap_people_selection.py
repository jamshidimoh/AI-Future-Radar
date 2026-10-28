"""Regression tests for post-bootstrap People signals staying in shared selection."""

from main import _merge_selected_people_candidates


def test_post_bootstrap_people_signals_are_not_force_appended():
    normal = {
        "title": "Important AI product launch",
        "link": "https://publisher.example/ai-launch",
        "people_lane": False,
        "final_editorial_score": 78.0,
    }
    selected_interview = {
        "title": "Andrew Ng discusses AI education",
        "link": "https://publisher.example/andrew-ng-interview",
        "people_lane": True,
        "content_type": "interview",
        "final_editorial_score": 66.0,
    }
    discovered_but_not_selected = {
        "title": "Jensen Huang confirms AI spending projection",
        "link": "https://publisher.example/jensen-spending",
        "people_lane": True,
        "people_bootstrap": False,
        "content_type": "news",
        # A source/person signal score is not a normal editorial score.
        "final_editorial_score": 0.09,
    }

    result = _merge_selected_people_candidates(
        [normal, selected_interview],
        [discovered_but_not_selected],
        bootstrap_mode=False,
    )

    assert [item["title"] for item in result] == [
        "Important AI product launch",
        "Andrew Ng discusses AI education",
    ]
    assert discovered_but_not_selected not in result


def test_bootstrap_candidates_are_retained_during_initial_baseline():
    selected = [{"title": "Regular news", "link": "https://publisher.example/news"}]
    bootstrap = [
        {
            "title": "One latest item for bootstrap person",
            "link": "https://publisher.example/bootstrap-person",
            "people_lane": True,
            "people_bootstrap": True,
            "people_bootstrap_validated": True,
        }
    ]

    result = _merge_selected_people_candidates(selected, bootstrap, bootstrap_mode=True)

    assert {item["title"] for item in result} == {
        "Regular news",
        "One latest item for bootstrap person",
    }
