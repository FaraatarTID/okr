Documentation HQ: [README](../../../README.md)

# T27 — Strict rollback execution evidence verification

Status: authorized narrow hardening after read-only inspection found that the strict verifier accepts an arbitrary nonempty `execution.observed_at` string.

## Current evidence

`rollback-execution-verification.yml` already attaches deployment output under `.execution` and invokes `scripts/verify_rollback_evidence.py --record`. No Darkube-specific workflow is needed. The verifier parses and timezone-validates `approved_at` but checks `observed_at` only for nonemptiness; malformed and timezone-less values can therefore pass.

## Owned files

- `scripts/verify_rollback_evidence.py`: parse `execution.observed_at` as ISO-8601 and require an explicit timezone, following the existing `approved_at` validation pattern.
- `tests/test_rollback_evidence.py`: add malformed and timezone-less invalid-record cases; retain the valid UTC `Z` case.
- `tests/test_rollback_workflow_wiring.py`: pin that the workflow attaches `.execution = $execution` as well as invoking `--record`.
- `task-T27-report.md`, `task-T27-snapshot.md`.

Do not change the workflow implementation, duplicate provider workflow, or claim a live paired rollback rehearsal. T10 is complete; its typing diagnostics and the exact T27 files should still be checked before editing.

## Acceptance

- Real CLI or verifier path rejects malformed and timezone-less `execution.observed_at` records.
- A timezone-aware valid record remains accepted.
- Workflow wiring test pins `.execution` attachment and `--record` invocation.
- Focused tests, scoped typing/lint, and diff checks pass. The live paired rollback rehearsal remains external/provider-gated.
