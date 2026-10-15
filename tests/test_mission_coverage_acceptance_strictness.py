"""Regression coverage for mission-coverage acceptance under runtime/provider failure."""

from scripts.production_acceptance_guard import _mission_coverage_status


def _coverage_log(attempts: str, summary: str = "[Mission Coverage Recovery] missing_lanes=1 attempts=1 recovered=0 status=unmet"):
    return (attempts + "\n" + summary).splitlines()


def test_candidate_processing_failure_is_not_misclassified_as_no_candidate():
    status = _mission_coverage_status(_coverage_log(
        "[Mission Coverage Recovery] attempt=1 area=mind_cognition title=Candidate status=failed"
    ))
    assert status is not None
    assert status["status"] == "unmet"
    assert status["no_candidate_lanes"] == 0
    assert status["nonpublishable_lanes"] == 1


def test_provider_outage_is_not_misclassified_as_no_candidate():
    status = _mission_coverage_status(_coverage_log(
        "[Mission Coverage Recovery] attempt=1 area=convergence title=Candidate status=provider_unavailable"
    ))
    assert status is not None
    assert status["no_candidate_lanes"] == 0
    assert status["nonpublishable_lanes"] == 1


def test_explicit_no_candidate_does_not_hide_failed_processing_in_same_lane():
    status = _mission_coverage_status(_coverage_log(
        "[Mission Coverage Recovery] area=mind_cognition status=no_candidate\n"
        "[Mission Coverage Recovery] attempt=1 area=mind_cognition title=Candidate status=failed"
    ))
    assert status is not None
    assert status["no_candidate_lanes"] == 0
    assert status["nonpublishable_lanes"] == 1


def test_only_below_score_floor_exhaustion_can_be_counted_as_nonpublishable_absence():
    status = _mission_coverage_status(_coverage_log(
        "[Mission Coverage Recovery] attempt=1 area=convergence title=Candidate status=below_score_floor"
    ))
    assert status is not None
    assert status["no_candidate_lanes"] == 1
    assert status["nonpublishable_lanes"] == 0


def test_explicit_no_candidate_without_processing_errors_is_accepted_as_absence():
    status = _mission_coverage_status(_coverage_log(
        "[Mission Coverage Recovery] area=mind_cognition status=no_candidate"
    ))
    assert status is not None
    assert status["no_candidate_lanes"] == 1


def test_successful_recovery_resolves_an_earlier_candidate_failure():
    status = _mission_coverage_status(_coverage_log(
        "[Mission Coverage Recovery] attempt=1 area=mind_cognition title=First status=failed\n"
        "[Mission Coverage Recovery] attempt=2 area=mind_cognition title=Replacement status=recovered"
    ))
    assert status is not None
    assert status["no_candidate_lanes"] == 0
    assert status["nonpublishable_lanes"] == 0
