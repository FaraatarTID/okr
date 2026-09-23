# T09 provider protocol split follow-up review

## Verdict

**FAIL — one runtime validation regression at `RestoreManager.__init__`.**

## Protocol shapes

The split itself matches manager use:

- `BackupManager` calls `provider_name`, `create_backup`, `verify_backup`, `get_backup_record`, and `record_status`; `BackupProvider` declares those members and no restore-only target-registration operation.
- `RestoreManager` calls those backup operations plus `is_target_registered`; `RestoreBackupProvider` adds that operation.
- When restore and backup adapters are combined, the runtime-checkable `RestoreProvider` contract adds `provider_name` and `restore_backup`. The fallback check ensures the backup adapter has the restore capability before it is used as the restore adapter.

## Finding

`RestoreManager.__init__` validates `restore_provider or backup_provider` but later selects the explicit adapter using `if restore_provider is None`. A falsey explicit restore adapter is therefore selected without being validated. This weakens the prior truthiness-based behavior and bypasses the production local-adapter guard.

Reproduction: pass a `ProductionBackup` with `provider_name = "production"` and an explicit `FalseyLocalRestore` (subclassing `LocalBackupProvider`, with `__bool__` returning `False`) with `production=True`. Construction succeeds and `manager.restore_provider` is the `local-isolated` adapter. The validation expression checked the production backup provider instead of the selected restore provider.

Validate the selected provider explicitly: choose the backup provider only when `restore_provider is None`, otherwise choose the supplied restore provider, then call `_validate_provider_for_environment` on that value. This keeps the explicit-`None` fallback and validates the actual adapter regardless of truthiness.

## Verification

- Mypy on `src/saas/backup_operations.py`: success, zero errors.
- `tests/test_saas_backup_operations.py`: 27 passed; current tests do not cover a falsey explicit restore adapter.
- The `MismatchedProvider` diagnostic in T10-owned tests was not inspected or changed in this review.
