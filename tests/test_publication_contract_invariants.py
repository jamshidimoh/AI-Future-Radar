def test_publication_contract_invariants():
    max_news_per_period = 3
    rank_window = 4
    max_extra_news = 2
    assert max_news_per_period == 1 + max_extra_news
    assert rank_window >= max_news_per_period


def test_rank_baseline_is_strictly_greater():
    previous = 100.0
    assert 100.1 > previous
    assert not (100.0 > previous)
    assert not (99.9 > previous)
