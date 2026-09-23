# T27 — Strict rollback execution evidence verification

## Result

Implemented the authorized local hardening. The verifier now requires `execution.observed_at` to parse as ISO-8601 and include an explicit timezone, consistent with its existing `approved_at` validation. The existing UTC `Z` record remains valid. The workflow wiring test now protects both the `.execution = $execution` attachment and the `--record` verifier call.

No workflow implementation or provider-specific route changed. The paired live rollback rehearsal remains provider-gated and unverified.

## Test-first evidence

Added malformed and timezone-less `observed_at` records to the invalid-record cases before modifying the verifier. The focused RED run failed on both cases because the verifier accepted them. After the minimal verifier change, the original valid UTC `Z` record and the new rejections pass. Independent review requested explicit missing-field coverage; an otherwise-valid execution object without `observed_at` is now included and rejected by the same verifier path.

## Verification

- `.venv\Scripts\python.exe -m pytest -q tests/test_rollback_evidence.py tests/test_rollback_workflow_wiring.py` — **55 passed** after the review follow-up.
- `.venv\Scripts\ruff.exe check scripts/verify_rollback_evidence.py tests/test_rollback_evidence.py tests/test_rollback_workflow_wiring.py` — **passed**.
- `.venv\Scripts\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip scripts/verify_rollback_evidence.py tests/test_rollback_evidence.py tests/test_rollback_workflow_wiring.py` — **passed**, no issues in 3 files. Mypy printed pre-existing unused-section warnings from `mypy.ini`.
- `git diff --check` — **exit 0**; Git printed existing line-ending notices for unrelated dirty files.

## Review boundary

No claim is made about a real Darkube operation, provider-issued outcome, or paired rollback rehearsal.

## Independent review

The follow-up review returned **PASS**: the missing `observed_at` case is pinned, and the focused suite passes 55 tests. The provider-backed paired rehearsal remains outside local scope.
