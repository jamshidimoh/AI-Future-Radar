from src.mission_selector import mission_score


def test_chatgpt_images_feature_is_routine_without_frontier_signal():
    item = {
        "title": "ChatGPT Images: Generate images at any size",
        "summary": "A new ChatGPT feature for generating images at any size.",
        "source": "YouTube - OpenAI",
        "content_type": "product_news",
        "editorial_score": 50,
        "signal_score": 0,
    }
    mission_score(item)
    assert item["routine_application_hits"] > 0
    assert item["routine_application_strong_signal"] is False


def test_new_model_remains_frontier_signal():
    item = {
        "title": "OpenAI releases a new model with a new reasoning capability",
        "summary": "The model demonstrates a new capability on a frontier benchmark.",
        "source": "OpenAI",
        "content_type": "product_news",
        "editorial_score": 50,
        "signal_score": 0,
    }
    mission_score(item)
    assert item["routine_application_strong_signal"] is True


def test_scientific_discovery_remains_frontier_signal():
    item = {
        "title": "AI system discovers a new scientific mechanism",
        "summary": "Experimental validation demonstrates a scientific discovery.",
        "source": "Nature",
        "content_type": "research",
        "editorial_score": 40,
        "signal_score": 0,
    }
    mission_score(item)
    assert item["routine_application_strong_signal"] is True
