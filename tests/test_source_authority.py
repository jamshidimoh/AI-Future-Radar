from src.source_authority import resolve_google_news_tier, resolve_source_tier


def test_unknown_google_news_publisher_cannot_inherit_tier1_query():
    assert resolve_google_news_tier("Finance Biggo", "https://finance.biggo.com/example") == 3


def test_known_tier1_publisher_is_promoted_by_verified_identity():
    assert resolve_google_news_tier("OpenAI", "https://openai.com/index/example/") == 1


def test_known_tier2_publisher_is_resolved_by_identity():
    assert resolve_google_news_tier("Business Insider", "https://www.businessinsider.com/example") == 2


def test_direct_configured_low_authority_tier_is_preserved():
    assert resolve_source_tier(source_name="Some configured source", configured_tier=3) == 3


def test_unknown_source_can_never_be_promoted_by_configured_tier():
    assert resolve_source_tier(source_name="Unknown Publisher", source_url="https://unknown.example", configured_tier=1) == 3


def test_lookalike_host_cannot_impersonate_tier1_domain():
    assert resolve_google_news_tier("OpenAI", "https://openai.com.evil.example/article") == 3


def test_new_first_party_research_and_engineering_publishers_resolve_to_tier1():
    assert resolve_source_tier(source_name="Microsoft Research", source_url="https://www.microsoft.com/en-us/research/feed/", configured_tier=1) == 1
    assert resolve_source_tier(source_name="Apple Machine Learning Research", source_url="https://machinelearning.apple.com/rss.xml", configured_tier=1) == 1
    assert resolve_source_tier(source_name="Engineering at Meta", source_url="https://engineering.fb.com/feed/", configured_tier=1) == 1
    assert resolve_source_tier(source_name="NVIDIA Developer Blog", source_url="https://developer.nvidia.com/blog/feed/", configured_tier=1) == 1
    assert resolve_source_tier(source_name="AWS Machine Learning Blog", source_url="https://aws.amazon.com/blogs/machine-learning/feed/", configured_tier=1) == 1


def test_interconnects_is_specialist_analysis_not_primary_research():
    assert resolve_source_tier(source_name="Interconnects AI", source_url="https://www.interconnects.ai/feed", configured_tier=2) == 2
