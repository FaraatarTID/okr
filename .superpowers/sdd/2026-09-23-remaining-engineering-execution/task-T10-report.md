Documentation HQ: [README](../../../README.md)

# T10 implementation report — test and script mypy slice

## Scope and result

Edited 13 owned test files. The two owned scripts and three other owned tests had no error in the exact file-only baseline, so they were left unchanged. No production, workflow, generated, T02/T03/T07, or ledger file was edited for T10.

The exact 18-file mypy invocation started at **48 errors in 13 files** and now reports **1 error in 1 file**. The remaining error is `tests/test_repository_readiness_workflow.py:13 [import-untyped]` for `yaml`. That untracked file belongs to T07 and was not edited. Excluding that T07 file, the exact 17-file invocation reports `Success: no issues found in 17 source files`. The earlier full-scope attribution of 106 errors is context dependent: analyzing imported product modules alongside these files reveals additional errors that `--follow-imports=skip` omits in a file-only invocation. This report does not claim that full-scope mypy is clean.

## Implementation

- Added local assertions for nested JSON fixture dictionaries before mutation in attestation, recovery, documented-evidence, and integration tests. The negative cases still mutate the same payloads.
- Replaced two side-effect lambdas whose `list.append` result was treated as a return value with named fakes that return the intended objects. Added precise annotations for empty collections, fallback payloads, and captured Playwright job responses.
- Kept the control-plane fake as an async instance method with an optional actor, matching its FastAPI dependency and avoiding method reassignment. Renamed the smoke handler's fixture map to avoid collision with `BaseHTTPRequestHandler.responses` and annotated the yielding fixture.
- Corrected a `BackupRecord.operator` test argument to its actual `str` contract and used `monkeypatch.setattr` for an intentionally altered provider method.
- Rebased the environment-mismatch provider fixture on `LocalBackupProvider`, overriding only `create_backup` to return a real provider record for `env-other`. The test still checks rejection and that no status was recorded.
- Four tests deliberately pass invalid strings into `BackupManager` or `RestoreManager` to prove runtime rejection. Each call has a line-local `# type: ignore[arg-type]` and an adjacent explanation. The invalid values and `pytest.raises` assertions remain intact. When `src/saas/operator_credentials.py` and `src/saas/backup_operations.py` are included in mypy's module set, `--warn-unused-ignores` does not flag these four ignores.

## Commands and evidence

Exact baseline/final command, run from repository root:

```powershell
$files = @('scripts/backup_saas_environment.py','scripts/restore_saas_environment.py','tests/test_attestation_verification.py','tests/test_control_plane_environment_routes.py','tests/test_cycle_single_active.py','tests/test_documented_evidence_schema.py','tests/test_e2e_playwright_spa_login_to_atlas.py','tests/test_generate_bff_allowlist.py','tests/test_migrate_tenant_databases.py','tests/test_prerelease_smoke.py','tests/test_read_path_budget.py','tests/test_recovery_evidence.py','tests/test_repository_readiness_workflow.py','tests/test_ritual_snapshot_rpc.py','tests/test_saas_backup_operations.py','tests/test_saas_integration_fix_wave.py','tests/test_saas_release_operations.py','tests/test_slo_probe_contracts.py')
.venv\Scripts\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip @files
```

Before: `Found 48 errors in 13 files (checked 18 source files)`, exit 1. After: `Found 1 error in 1 file (checked 18 source files)`, exit 1, solely T07's missing PyYAML stub. The same command without `tests/test_repository_readiness_workflow.py`: `Success: no issues found in 17 source files`, exit 0.

Focused tests: `.venv\Scripts\pytest.exe -q` over all 13 changed test files: **165 passed, 3 skipped**, exit 0 before the final fixture adjustment. After that adjustment, `.venv\Scripts\pytest.exe -q tests/test_saas_integration_fix_wave.py` reported **29 passed**, exit 0. The three E2E skips require their opt-in environment. Existing warnings: Starlette/httpx deprecation and pytest cache write permission. Ruff on the changed files: `All checks passed!`, exit 0. `git diff --check` on the pre-review diff: exit 0.

## Review and follow-up

An expanded mypy context with `src/saas/operator_credentials.py` and `src/saas/backup_operations.py` consumes the four narrow ignores. The initial expanded run exposed three provider protocol errors. T09 corrected the product protocol so `BackupManager` does not require a restore-only method, and this T10 follow-up rebased the mismatch fixture on the real local provider. A fresh expanded command now passes: `.venv\Scripts\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip --warn-unused-ignores src/saas/operator_credentials.py src/saas/backup_operations.py tests/test_saas_backup_operations.py tests/test_saas_integration_fix_wave.py` → `Success: no issues found in 4 source files`, exit 0.

Independent reviewer should scrutinize the four line-local `arg-type` ignores, the async control-plane fake, and the reworked mismatch fixture in particular.

## Full-scope follow-up

The full repository command was rerun before edits and saved in `task-T10-fullscope-baseline.txt`:

```powershell
.venv\Scripts\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip backend_app src scripts tests
```

Baseline: **16 errors in 5 files**, exit 1, checked 379 source files. Thirteen errors belonged to T10-owned tests: eight in `test_saas_integration_fix_wave.py` (method reassignment and two deliberate invalid operators), four in `test_read_path_budget.py` (nullable generated IDs), and one in `test_saas_release_operations.py` (nullable current artifact). The other three were in T02/T32-reserved read helpers.

The follow-up replaced direct provider-method assignments with `monkeypatch.setattr`; the two failure fakes now raise explicitly with matching return signatures. The remaining deliberate invalid operator arguments in Provisioner and ReleaseManager have line-local `arg-type` ignores, matching the existing BackupManager/RestoreManager negative cases. Read-budget fixtures assert generated IDs exist before use. The release test asserts the reloaded current artifact exists before checking its version.

Fresh full-scope output is saved in `task-T10-fullscope-after.txt`: **3 errors in 2 files**, exit 1, checked 379 source files. All three are reserved for T02/T32: `src/services/supabase_api_mode_read.py:575 [no-redef]`, `backend_app/read_query_helpers.py:194 [arg-type]`, and `backend_app/read_query_helpers.py:553 [arg-type]`. There are zero remaining full-scope diagnostics in T10-owned files.

Focused verification after these edits: `.venv\Scripts\pytest.exe -q tests/test_saas_integration_fix_wave.py tests/test_read_path_budget.py tests/test_saas_release_operations.py` → **52 passed**, exit 0. Ruff on those three files: `All checks passed!`, exit 0. `git diff --check` on those three files: exit 0. The test run emitted the existing Starlette/httpx deprecation and pytest-cache write warnings.
