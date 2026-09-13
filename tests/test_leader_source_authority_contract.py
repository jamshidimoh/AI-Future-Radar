from main import _leader_source_authority


def test_authority_maps_source_tier_to_higher_is_better():
    assert _leader_source_authority({"source": "official", "source_tier": 1}) == 3
    assert _leader_source_authority({"source": "Reuters", "source_tier": 2}) == 2
    assert _leader_source_authority({"source": "other", "source_tier": 3}) == 1


def test_authority_uses_source_tier_correction():
    assert _leader_source_authority({"source": "Google News (Bitcoin World)", "source_tier": 1}) == 1
