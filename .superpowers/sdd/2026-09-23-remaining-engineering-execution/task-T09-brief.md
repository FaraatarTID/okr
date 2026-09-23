# T09 — Mypy burn-down: runtime core

## Objective and baseline

Reduce type errors in the assigned `src` slice using
`mypy --no-incremental --ignore-missing-imports --follow-imports=skip`.
Current full-scope remeasurement on 2026-09-23 found 160 errors in 31 files.
This slice owns 39 current errors in nine files; the `supabase_api_mode_read.py`
error is reserved for T02 and must not be touched here.

## Exact owned files

- `src/crud_auth_helpers.py` (4 errors)
- `src/saas/backup_operations.py` (15)
- `src/saas/environment_contract.py` (1)
- `src/saas/file_lock.py` (5)
- `src/saas/operator_credentials.py` (3)
- `src/saas/provisioning.py` (3)
- `src/saas/release_operations.py` (5)
- `src/services/app_shell_runtime.py` (2)
- `src/utils/sync.py` (1)

Do not edit `src/services/supabase_api_mode_read.py`, identity/session files,
generated contracts, or files assigned to another packet.

## Acceptance

- Remove the existing errors in the owned files without broad suppressions,
  unchecked casts, or type lies that hide runtime contracts.
- Add/adapt focused tests only where needed to preserve behavior; retain strong
  validation on external input and nullable values.
- Run exact mypy command for the owned files and report before/after counts plus
  focused tests for changed behavior.
- Do not edit QG-002 milestone policy or shared progress ledger.

## Workflow

One implementer, independent reviewer, serial per-file ownership. Preserve user
changes. `.git` is read-only: no branches, worktrees, index, or commits.
