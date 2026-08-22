from period_ranked_pipeline import _global_ranked_selection


def test_rank_news_orders_by_final_score_and_assigns_period_rank():
    items = [
        {"id": "b", "editorial_score": 81, "title": "B", "summary": "متن فارسی", "why_it_matters": "اهمیت"},
        {"id": "a", "editorial_score": 95, "title": "A", "summary": "متن فارسی", "why_it_matters": "اهمیت"},
        {"id": "c", "editorial_score": 88, "title": "C", "summary": "متن فارسی", "why_it_matters": "اهمیت"},
    ]
    ranked = _global_ranked_selection(items, 4, 2, 2, {})
    assert [x["id"] for x in ranked] == ["a", "c", "b"]
    assert [x["period_rank"] for x in ranked] == [1, 2, 3]
    assert [x["normal_period_rank"] for x in ranked] == [1, 2, 3]


def test_duplicate_is_removed_before_ranking():
    items = [
        {"id": "dup", "editorial_score": 100, "duplicate": True, "title": "تکراری", "summary": "فارسی", "why_it_matters": "اهمیت"},
        {"id": "ok", "editorial_score": 90, "title": "خبر", "summary": "متن فارسی", "why_it_matters": "اهمیت"},
    ]
    ranked = _global_ranked_selection(items, 4, 2, 2, {})
    assert [x["id"] for x in ranked] == ["ok"]


def test_tier0_interviews_are_global_first_but_do_not_consume_normal_rank_window():
    items = [
        {"id": "normal1", "editorial_score": 95, "title": "خبر", "summary": "متن فارسی", "why_it_matters": "اهمیت"},
        {"id": "person1", "editorial_score": 50, "title": "Sam Altman interview", "content_type": "interview", "leader": "Sam Altman", "summary": "یک گفتگوی طولانی درباره مدل‌ها، ایجنت‌ها، ایمنی و آینده هوش مصنوعی با جزئیات کافی.", "why_it_matters": "اهمیت"},
        {"id": "person2", "editorial_score": 49, "title": "Elon Musk interview", "content_type": "interview", "leader": "Elon Musk", "summary": "یک گفتگوی طولانی درباره مدل‌ها، زیرساخت، عامل‌های هوشمند و آینده هوش مصنوعی با جزئیات کافی.", "why_it_matters": "اهمیت"},
        {"id": "normal2", "editorial_score": 90, "title": "خبر دوم", "summary": "متن فارسی", "why_it_matters": "اهمیت"},
    ]
    ranked = _global_ranked_selection(items, 4, 2, 2, {})
    assert ranked[0]["id"] == "person1"
    assert ranked[1]["id"] == "person2"
    normal = [x for x in ranked if x["normal_period_rank"] is not None]
    assert [x["normal_period_rank"] for x in normal] == [1, 2]
    assert [x["period_rank"] for x in normal] == [3, 4]
