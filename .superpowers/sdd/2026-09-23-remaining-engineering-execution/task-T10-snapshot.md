# T10 review snapshot

Base: shared checkout before T10 edits, without Git writes. Review only the 13 test diffs listed below plus `task-T10-report.md`. T10 made no production or script changes and did not edit the shared progress ledger.

| Files | Review focus |
| --- | --- |
| `tests/test_attestation_verification.py`, `tests/test_recovery_evidence.py`, `tests/test_documented_evidence_schema.py` | Checked nested dictionary fixture access preserves payload mutation and signing order. |
| `tests/test_control_plane_environment_routes.py` | Async instance dependency and optional actor preserve authenticated and unauthenticated route cases. |
| `tests/test_cycle_single_active.py`, `tests/test_migrate_tenant_databases.py`, `tests/test_saas_integration_fix_wave.py` | Named fakes preserve side effects and return values. Integration file also has a checked attestation section and two intentional invalid-credential calls. |
| `tests/test_prerelease_smoke.py`, `tests/test_e2e_playwright_spa_login_to_atlas.py`, `tests/test_ritual_snapshot_rpc.py` | Fixture map name, yielded fixture type, captured event shape, and fallback payload type. |
| `tests/test_generate_bff_allowlist.py`, `tests/test_slo_probe_contracts.py` | Precise empty collection annotations. |
| `tests/test_saas_backup_operations.py` | `BackupRecord.operator` string, method monkeypatch, and two intentional invalid-credential calls. |

The exact 18-file mypy result retains one T07-owned PyYAML-stub error. After T09's source contract correction and the scoped T10 fixture update, expanded mypy with the credential and backup modules plus two owned tests passes with `--warn-unused-ignores` (4 source files). Full focused pytest before the fixture update: 165 passed, 3 skipped. The changed integration file after the update: 29 passed. Ruff passes.

Full-scope follow-up review delta: inspect only `tests/test_saas_integration_fix_wave.py`, `tests/test_read_path_budget.py`, and `tests/test_saas_release_operations.py` against the previous T10 snapshot. The first uses method monkeypatches and two additional narrow invalid-operator ignores; the second asserts generated IDs before passing them to typed CRUD functions; the third narrows an optional current artifact. `task-T10-fullscope-baseline.txt` and `task-T10-fullscope-after.txt` show the exact repository command moving from 16 errors (13 T10, 3 reserved) to 3 errors (all reserved). The three affected test files report 52 passed; Ruff and diff checks pass.
