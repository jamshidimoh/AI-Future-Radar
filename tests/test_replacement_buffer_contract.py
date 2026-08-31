from src.unified_editorial_selection import load_editorial_contract


def test_replacement_buffer_is_configured_for_production():
    contract = load_editorial_contract()
    assert contract["replacement_buffer"] == 2
    assert contract["candidate_window"] == 6
