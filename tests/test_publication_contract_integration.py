def select_for_publication(items, previous_score):
    ranked = sorted(items, key=lambda x: x["score"], reverse=True)[:4]
    for rank, item in enumerate(ranked, 1):
        item["period_rank"] = rank
    selected = [ranked[0]] if ranked else []
    if previous_score is not None:
        selected.extend(x for x in ranked[1:4] if x["score"] > previous_score)
    return selected[:3]


def test_rank_one_plus_two_extras():
    result = select_for_publication(
        [{"id": "a", "score": 110}, {"id": "b", "score": 109}, {"id": "c", "score": 108}, {"id": "d", "score": 99}],
        100,
    )
    assert [x["period_rank"] for x in result] == [1, 2, 3]


def test_no_extra_below_baseline():
    result = select_for_publication(
        [{"id": "a", "score": 110}, {"id": "b", "score": 99}, {"id": "c", "score": 98}],
        100,
    )
    assert [x["period_rank"] for x in result] == [1]
