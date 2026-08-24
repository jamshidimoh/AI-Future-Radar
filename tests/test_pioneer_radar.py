import sqlite3
import tempfile
from pathlib import Path

from pioneer_radar.epistemic_tensions import related_opponents, tension_for_person
from pioneer_radar.portfolio_safeguard import analytical_anchor, filter_without_anchor
from pioneer_radar.prediction_ledger import add_claim, connect, recent_claims, record_outcome
from pioneer_radar.pioneer_scoring import pioneer_score
from pioneer_radar.source_priority import source_weight


def test_deep_sources_outrank_social_triggers():
    assert source_weight({"source_format": "full_paper"}) > source_weight({"source_format": "social_post"})
    assert source_weight({"source_format": "full_transcript"}) > source_weight({"source_format": "news_report"})


def test_pioneer_score_uses_influence_and_future_factors():
    high = pioneer_score({"technology_impact": 10, "scientific_authority": 10, "future_vision": 10, "public_influence": 10, "trend_score": 10, "audience_score": 10})
    assert high == 100.0


def test_tension_matrix_returns_opponents():
    assert "Yann LeCun" in related_opponents("Sam Altman")
    assert tension_for_person("David Chalmers")


def test_no_news_without_analytical_anchor():
    plain = {"title": "routine product update"}
    anchored = {"title": "new research breakthrough", "research_signal": True}
    ok, reasons = analytical_anchor(anchored)
    assert ok and "research" in reasons
    kept, rejected = filter_without_anchor([plain, anchored])
    assert kept == [anchored]
    assert rejected == [plain]


def test_prediction_ledger_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "pioneer_memory.db"
        conn = connect(db)
        claim_id = add_claim(conn, person="Sam Altman", claim="AGI will arrive soon", topic="AGI", claim_date="2026-01-01")
        assert recent_claims(conn, "Sam Altman", "AGI")[0]["id"] == claim_id
        record_outcome(conn, claim_id, status="falsified", evaluated_date="2028-01-01", outcome="did not materialize")
        assert recent_claims(conn, "Sam Altman", "AGI")[0]["status"] == "falsified"
        conn.close()
