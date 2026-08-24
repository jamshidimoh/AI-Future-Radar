from src.period_publication_contract import rank_period_candidates, select_news_for_period


def test_rank_one_only_without_baseline():
    items = [{"id":"a","score":90},{"id":"b","score":80}]
    assert [x["id"] for x in select_news_for_period(items, None)] == ["a"]


def test_max_three_with_two_stronger_extras():
    items = [{"id":"a","score":95},{"id":"b","score":94},{"id":"c","score":93},{"id":"d","score":92},{"id":"e","score":91}]
    assert [x["id"] for x in select_news_for_period(items, 90)] == ["a","b","c"]


def test_only_ranks_two_to_four_can_be_extras():
    items = [{"id":"a","score":100},{"id":"b","score":70},{"id":"c","score":81},{"id":"d","score":82},{"id":"e","score":99}]
    assert [x["id"] for x in select_news_for_period(items, 80)] == ["a","e","d"]


def test_quality_gate_prevents_primary_publication():
    items = [{"id":"bad","score":100,"quality_gate":False},{"id":"good","score":90}]
    assert [x["id"] for x in select_news_for_period(items, 80)] == ["good"]


def test_duplicates_are_hard_blocked():
    items = [{"id":"dup","score":100,"duplicate":True},{"id":"good","score":90}]
    assert [x["id"] for x in select_news_for_period(items, 80)] == ["good"]


def test_tier0_does_not_consume_normal_rank_window():
    items = [
        {"id":"person","score":150,"title":"Sam Altman interview", "content_type":"interview", "leader":"Sam Altman", "summary":"یک گفتگوی طولانی درباره مدل‌ها، ایجنت‌ها، ایمنی و آینده هوش مصنوعی با جزئیات کافی."},
        {"id":"a","score":100},
        {"id":"b","score":99},
    ]
    ranked = rank_period_candidates(items)
    assert ranked[0]["id"] == "person"
    assert ranked[0]["tier0_rank"] == 1
    assert ranked[1]["normal_period_rank"] == 1
    assert ranked[2]["normal_period_rank"] == 2
    assert [x["id"] for x in select_news_for_period(items, 90)] == ["a", "b"]
