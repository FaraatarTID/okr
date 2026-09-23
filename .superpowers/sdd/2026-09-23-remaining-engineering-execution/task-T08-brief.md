Documentation HQ: [README](../../../README.md)

# T08 — Mypy burn-down: backend app

## Objective and baseline

Reduce type errors in the assigned `backend_app` slice using
`mypy --no-incremental --ignore-missing-imports --follow-imports=skip`.
Current full-scope remeasurement on 2026-09-23 found 160 errors in 31 files.
This slice owns 12 errors in two files; the two `read_query_helpers.py` errors
are reserved for T02/T32 and must not be touched here.

## Exact owned files

- `backend_app/main.py` (6 current errors)
- `backend_app/observability_http.py` (6 current errors)

Do not edit `backend_app/read_query_helpers.py`, `backend_app/response_scope_helpers.py`,
`backend_app/routers/**`, shared generated artifacts, or another task's tests.

## Acceptance

- Remove the existing errors in both owned files without `Any`/`cast`/ignore
  shortcuts that erase runtime validation or weaken contracts.
- Add or adapt focused tests only where a behavior change is necessary; preserve
  the existing request/runtime contracts.
- Run the exact mypy command against both owned files and report before/after
  error counts, plus focused tests for any changed behavior.
- No unrelated files or QG-002 milestone policy edits.

## Workflow

One implementer, independent reviewer, serial per-file ownership. Preserve user
changes. `.git` is read-only: no branches, worktrees, index, or commits. Do not
edit the shared progress ledger.
