from src.editorial_score_v2 import (
    build_features,
    is_major_ai_product_release,
    is_strategic_leader_statement,
    score_editorial_v2,
)


def test_interactive_world_simulator_launch_is_a_major_product_signal():
    item = {
        "title": "Google DeepMind introduces Genie 4, an interactive world simulator",
        "summary": "The new world model generates interactive environments in real time.",
        "source": "Google DeepMind",
        "source_tier": 1,
        "content_type": "product_news",
        "_ai_link": True,
        "evidence_text": "Official product announcement",
        "freshness_hours": 3,
    }
    assert is_major_ai_product_release(item) is True
    assert build_features(item)["publication_value"] == 1.0


def test_consequential_ai_leader_statement_about_electricity_is_prioritized():
    item = {
        "title": "Elon Musk: electricity, not chips, will limit AI growth",
        "summary": "Musk says data-center power demand and compute infrastructure are strategic constraints.",
        "source": "Reuters",
        "source_tier": 1,
        "content_type": "leader_signal",
        "watch_person": "Elon Musk",
        "_ai_link": True,
        "evidence_text": "Attributed report",
        "freshness_hours": 4,
    }
    assert is_strategic_leader_statement(item) is True
    assert build_features(item)["publication_value"] == 0.95


def test_generic_company_partnership_does_not_get_product_launch_priority():
    generic = {
        "title": "Google DeepMind announces a corporate partnership",
        "summary": "The organizations will work together on a business initiative.",
        "source": "Google DeepMind",
        "source_tier": 1,
        "content_type": "news",
        "_ai_link": True,
        "evidence_text": "Company announcement",
        "freshness_hours": 3,
    }
    assert is_major_ai_product_release(generic) is False
    assert build_features(generic)["publication_value"] == 0.70


def test_major_product_launch_and_strategic_statement_outscore_generic_company_news():
    baseline = {
        "title": "Google DeepMind announces a corporate partnership",
        "summary": "The organizations will work together on a business initiative.",
        "source": "Google DeepMind",
        "source_tier": 1,
        "content_type": "news",
        "_ai_link": True,
        "evidence_text": "Company announcement",
        "freshness_hours": 3,
    }
    product = {
        **baseline,
        "title": "Google DeepMind introduces Genie 4, an interactive world simulator",
        "summary": "The new world model generates interactive environments in real time.",
        "content_type": "product_news",
    }
    strategic = {
        **baseline,
        "title": "Elon Musk: electricity, not chips, will limit AI growth",
        "summary": "Musk says data-center power demand and compute infrastructure are strategic constraints.",
        "source": "Reuters",
        "content_type": "leader_signal",
        "watch_person": "Elon Musk",
    }
    base_score, _ = score_editorial_v2(baseline)
    product_score, _ = score_editorial_v2(product)
    strategic_score, _ = score_editorial_v2(strategic)
    assert product_score > base_score
    assert strategic_score > base_score

def test_persian_attributed_statement_about_ai_electricity_is_prioritized():
    item = {
        "title": "ایلان ماسک: محدودیت آینده هوش مصنوعی، تراشه نیست؛ برق است",
        "summary": "او هشدار می‌دهد که تأمین برق و زیرساخت مراکز داده می‌تواند سرعت توسعهٔ هوش مصنوعی را محدود کند.",
        "source": "منبع خبری معتبر",
        "source_tier": 1,
        "content_type": "news",
        "_ai_link": True,
        "evidence_text": "گزارش منبع",
        "freshness_hours": 4,
    }
    assert is_strategic_leader_statement(item) is True
    assert build_features(item)["publication_value"] == 0.95
