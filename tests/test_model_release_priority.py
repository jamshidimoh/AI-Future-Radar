from src.model_release_priority import is_major_model_release, model_release_bonus


def test_major_model_release_gets_priority():
    item = {
        "title": "OpenAI launches GPT-5.6",
        "content_type": "product_news",
        "summary": "OpenAI announced GPT-5.6 with a new reasoning capability and immediate availability.",
        "source": "OpenAI",
    }
    assert is_major_model_release(item)
    assert model_release_bonus(item) == 32.0


def test_generic_company_news_is_not_model_release():
    item = {
        "title": "OpenAI announces a new partnership",
        "content_type": "news",
        "summary": "OpenAI announced a strategic partnership with another company.",
        "source": "OpenAI",
    }
    assert not is_major_model_release(item)


def test_generic_new_version_phrase_is_not_enough():
    item = {
        "title": "Microsoft announces a new version of its platform",
        "content_type": "news",
        "summary": "The company announced a new version of a software platform, without a model name or model-release language.",
        "source": "Microsoft",
    }
    assert not is_major_model_release(item)


def test_gemini_flash_release_is_detected():
    item = {
        "title": "Google unveils Gemini 3.7 Flash",
        "content_type": "official",
        "summary": "Google introduced Gemini 3.7 Flash for coding and agent workflows and made it available to users.",
        "source": "Google DeepMind",
    }
    assert is_major_model_release(item)


def test_model_identifier_scan_handles_long_text_without_backtracking():
    item = {
        "title": "OpenAI platform update",
        "content_type": "news",
        "summary": ("OpenAI announced a broad platform update. " * 5000)
        + " The release also documents compatibility notes and deployment guidance.",
        "source": "OpenAI",
    }
    assert not is_major_model_release(item)


def test_common_model_variants_are_detected():
    cases = [
        ("Qwen3.8", "Alibaba releases Qwen3.8"),
        ("GPT-OSS-120B", "OpenAI releases GPT-OSS-120B"),
        ("Claude Sonnet 4", "Anthropic launches Claude Sonnet 4"),
        ("Gemini 3.7 Flash", "Google launches Gemini 3.7 Flash"),
    ]
    for _, title in cases:
        item = {"title": title, "content_type": "product_news", "source": title.split()[0]}
        assert is_major_model_release(item)
