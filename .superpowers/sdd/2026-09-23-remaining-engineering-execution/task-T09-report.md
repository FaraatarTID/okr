# T09 implementation report — runtime core mypy slice

## Scope and result

Changed only the nine reserved `src` files. The full-scope baseline assigned 39 errors to this slice: 34 shown by the nine-file invocation plus four in `src/crud_auth_helpers.py` and one in `src/utils/sync.py` that appeared when `src` was analyzed as a package. The nine-file invocation alone did not show the latter five. Fresh full-scope mypy output now has **zero diagnostics in the nine reserved files**. The full workspace still has errors owned by other packets.

## Changes

- Made the manifest version literal and resolved optional credential inputs to concrete strings before validation.
- Selected the Windows or Unix file-lock implementation with `sys.platform`, which mypy can narrow on both platforms.
- Narrowed nullable state paths and control-plane references at their internal use points. Typed the provisioner control plane and orphan payload according to their actual contracts.
- Typed the snapshot registry against the `clear()` operation shared by keyed and unkeyed caches, then supplied the three concrete caches before adding the registry.
- Matched backup and restore operator parameters to their runtime credential checks; verified the backup provider implements the restore protocol before using it as the restore fallback. Gave datetime values distinct names from status timestamps.
- Checked normalized auth-throttle timestamps before subtraction and read the runtime helper's `object` user through its `id` attribute explicitly.

## Verification

- `.venv\Scripts\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip` with the nine reserved file paths: initial **34 errors in seven files**; final **success, zero errors in nine files**.
- Same mypy flags on `src`: final **one error in `src/services/supabase_api_mode_read.py`**, reserved for T02; zero T09 errors. The four auth helper and one sync error observed before the final edits are gone.
- Same mypy flags on `backend_app src scripts tests`: final **26 errors in seven files**, zero T09 source-file errors. This is a moving workspace with concurrent packets, so the global count is not a controlled before/after comparison.
- `mypy --platform linux` with the same flags on `src/saas/file_lock.py`: success, zero errors.
- Focused pytest command covering backup, release, provisioning, operator credentials, SaaS integration, facade cache, database integrity, and auth throttle behavior: **138 passed**, two existing warnings (Starlette/httpx deprecation and pytest cache permission).
- Ruff on all nine reserved files: all checks passed. `git diff --check` on those files: exit 0.

## Cross-packet diagnostics

Four stricter constructor `arg-type` errors are now visible in T10-owned negative tests: `tests/test_saas_backup_operations.py:297,299` and `tests/test_saas_integration_fix_wave.py:510,514`. They intentionally pass forged strings and assert runtime rejection. Those tests were not edited because T09 owns only the nine source files. The full-scope output also includes other pre-existing or concurrently changed errors, including the T02-owned `supabase_api_mode_read.py` name redefinition.

## Review handoff

The implementation snapshot is `task-T09-review.diff`. No Git index, commit, shared ledger, or non-reserved source/test file was written.

## Scoped follow-up: restore target capability

T10 found that the original `BackupProvider` protocol required `is_target_registered()` even for `BackupManager` callers. That method is used only by `RestoreManager`. I split the contract in `src/saas/backup_operations.py`: `BackupProvider` contains backup creation and verification methods; `RestoreBackupProvider` extends it with the registered-target check, and `RestoreManager` requires the latter. Runtime behavior is unchanged.

Fresh focused mypy on `src/saas/backup_operations.py`, `tests/test_saas_backup_operations.py`, and `tests/test_saas_integration_fix_wave.py` now reports **one** diagnostic: the `MismatchedProvider` test fixture at `tests/test_saas_integration_fix_wave.py:419` omits `get_backup_record()` and `verify_backup()`, which `BackupManager.verify()` actually calls. The two `MinimalProviderWithoutStatus` errors in `tests/test_saas_backup_operations.py` are gone. Focused pytest on these two test files: **56 passed**; Ruff on `backup_operations.py`: all checks passed. The remaining fixture change belongs to T10 and was left untouched.

## Reviewer correction: validate the selected restore provider

Independent review found that `RestoreManager` validated `restore_provider or backup_provider` but selected the explicit adapter using `is None`. A falsey explicit restore adapter could therefore bypass the production-local-adapter guard. The T09-owned regression test is `tests/test_restore_provider_truthiness.py`. It uses a falsey local restore adapter and a production-named backup adapter. Before the fix, the test failed because construction with `production=True` did not raise. After selecting the fallback only when the explicit adapter is `None` and validating the selected adapter, the test passes.

Fresh focused verification: `pytest -q -p no:cacheprovider tests/test_restore_provider_truthiness.py tests/test_saas_backup_operations.py tests/test_saas_integration_fix_wave.py` → **57 passed**; mypy on `src/saas/backup_operations.py` and the new test → zero errors; Ruff on both → clean. The new test file is owned by T09 and disjoint from T10's reserved files.
