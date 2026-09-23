# T09 provider protocol follow-up re-review

## Verdict

**PASS.** The falsey-provider selection/validation regression is fixed.

## Findings

`RestoreManager.__init__` now uses `restore_provider is None` to decide whether to fall back to `backup_provider`. The fallback path first checks that the backup provider structurally implements `RestoreProvider`. It then validates the selected provider with `_validate_provider_for_environment` before storing it. An explicitly supplied falsey provider is no longer replaced or skipped during validation.

The regression test covers both relevant outcomes: a falsey local provider is selected when production restrictions are off, and the same selected provider is rejected when `production=True`. This matches the provider selection contract and closes the previous bypass.

## Verification

- `tests/test_restore_provider_truthiness.py` and `tests/test_saas_backup_operations.py`: **28 passed**.
- Mypy on `src/saas/backup_operations.py`: **success, zero errors**.
- Pytest emitted the existing cache-path permission warning.

No source or shared-ledger changes were made by this review. T10-owned `MismatchedProvider` work remains outside scope.
