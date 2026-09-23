Documentation HQ: [README](../../../README.md)

# T10 — Mypy burn-down: tests and scripts

## Objective and baseline

Reduce type errors in the assigned test/script slice using
`mypy --no-incremental --ignore-missing-imports --follow-imports=skip`.
Current full-scope remeasurement on 2026-09-23 found 160 errors in 31 files.
This slice owns 106 current errors in the exact files below. The counts are
baseline findings, not a requirement to erase meaningful types with suppressions.

## Exact owned files

Scripts:

- `scripts/backup_saas_environment.py`
- `scripts/restore_saas_environment.py`

Tests:

- `tests/test_attestation_verification.py`
- `tests/test_control_plane_environment_routes.py`
- `tests/test_cycle_single_active.py`
- `tests/test_documented_evidence_schema.py`
- `tests/test_e2e_playwright_spa_login_to_atlas.py`
- `tests/test_generate_bff_allowlist.py`
- `tests/test_migrate_tenant_databases.py`
- `tests/test_prerelease_smoke.py`
- `tests/test_read_path_budget.py`
- `tests/test_recovery_evidence.py`
- `tests/test_repository_readiness_workflow.py`
- `tests/test_ritual_snapshot_rpc.py`
- `tests/test_saas_backup_operations.py`
- `tests/test_saas_integration_fix_wave.py`
- `tests/test_saas_release_operations.py`
- `tests/test_slo_probe_contracts.py`

Do not edit other scripts/tests, generated files, shared workflows, or files
reserved to T02/T03/T07. In particular, T03's actor-presence tests are outside
this current mypy error set and remain T03-owned.

## Acceptance

- Reduce the assigned errors without broad `Any`, blanket ignores, weakened
  runtime assertions, or test-specific type lies. Prefer precise TypedDicts,
  Protocols, and annotations that match actual fixture shapes.
- Run exact mypy command for the owned files and report before/after error
  counts; run focused tests for changed fixtures/contracts.
- Report any baseline error that proves to require product-code scope beyond
  the owned files before touching it.
- Do not edit QG-002 milestone policy or shared progress ledger.

## Workflow

One implementer, independent reviewer, serial per-file ownership. Preserve user
changes. `.git` is read-only: no branches, worktrees, index, or commits.
