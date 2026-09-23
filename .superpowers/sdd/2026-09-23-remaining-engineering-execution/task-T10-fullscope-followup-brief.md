# T10 follow-up — clear remaining full-scope mypy diagnostics

## Objective and ownership

After T08–T10 and the T07 typing follow-up settled, the exact repository-wide
QG-002 command still reports diagnostics in three T10-owned files, in addition
to three errors reserved for T02/T32. Clear only diagnostics in T10's originally
reserved test/script files; do not edit `backend_app/read_query_helpers.py` or
`src/services/supabase_api_mode_read.py` (T02/T32 lane), T07's workflow test, or
any other packet's files.

Current T10-owned full-scope locations include:

- `tests/test_saas_integration_fix_wave.py`: direct provider-method
  reassignment around lines 85/165/168 and invalid string operators around
  lines 488/493 (line numbers may shift as earlier fixes are retained).
- `tests/test_read_path_budget.py`: four `int | None` arguments around lines
  147/151/156/157.
- `tests/test_saas_release_operations.py`: optional artifact dereference around
  line 168.

Re-run the full command before editing to capture the exact current diagnostics;
the locations above are a handoff, not a frozen claim.

## Acceptance

- Remove all diagnostics in exact T10-owned files in a fresh full-scope mypy
  run. Leave only the three explicitly reserved T02/T32 diagnostics if present.
- Fix types at truthful test seams: retain runtime negative cases, use explicit
  narrowing/assertions for optional values, and avoid broad casts/ignores or
  contract weakening.
- Run focused tests for changed files, Ruff, and record fresh full-scope count.
- Do not edit the shared progress ledger. `.git` is read-only; no branch,
  worktree, index write, or commit.
