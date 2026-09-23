Documentation HQ: [README](../../../README.md)

# T09 independent review

## Verdict

**PASS**, with four cross-packet test diagnostics recorded below. No blocking finding in the nine T09-owned source files.

## Scope checked

Reviewed the implementation against `task-T09-brief.md` and the implementation snapshot. Confirmed changes are limited to the nine reserved `src` files. No broad suppressions, unchecked casts, or type-only contract weakening were found.

The operator constructor annotations now accept `OperatorCredential | None`, and the existing runtime checks still require an actual `OperatorCredential` before saving its principal. `_require_operator` retains the same enforcement for backup and restore. The string values in the four negative tests are still rejected at runtime; their static diagnostics are in T10-owned tests and are not masked here.

Other nullable values are narrowed by explicit checks or assertions at guarded internal call sites. The restore fallback performs a runtime `RestoreProvider` protocol check before assigning the backup provider to the restore slot. The cache registry's `clear()` protocol describes both concrete cache types and its construction excludes the registry itself, preserving invalidation behavior.

## Verification

- Exact nine-file mypy command from the brief: **success, zero errors in nine source files**.
- `tests/test_saas_backup_operations.py`, `tests/test_saas_provisioning.py`, `tests/test_saas_release_operations.py`, `tests/test_facade_service_boundary.py`: **84 passed**.
- `tests/test_saas_operator_credentials.py`, `tests/test_login_throttle_key.py`, `tests/test_auth_rate_limit.py`: **18 passed**.
- Two pytest invocations emitted the existing pytest cache permission warning; the auth suite also emitted a Starlette/httpx deprecation warning.

## Cross-packet note

The four expected strict-constructor `arg-type` errors remain in T10-owned negative tests at `tests/test_saas_backup_operations.py:297,299` and `tests/test_saas_integration_fix_wave.py:510,514`. They test runtime rejection of strings and were not changed in this review. Coordinate their typing treatment with T10 without weakening the T09 source contract.
