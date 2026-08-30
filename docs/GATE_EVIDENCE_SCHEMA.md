# Gate Evidence Schema

A gate may advance only when the result is tied to the exact revision that was tested.

Required fields:

- `gate`: gate identifier (`G0` ... `G9`)
- `commit_sha`: exact tested revision
- `workflow_run_id`: GitHub Actions run identifier
- `test_result`: PASS/FAIL
- `acceptance_result`: PASS/FAIL
- `timestamp_utc`: evidence creation time
- `notes`: concise human-readable audit context

A missing or mismatched field is a validation failure. Evidence is append-oriented and must not overwrite prior failures.

`PASS` means evidence exists and all required checks passed. `VALIDATION_PENDING` means implementation exists but acceptance evidence is incomplete. `BLOCKED` means execution cannot proceed safely.
