# Launcher and Runtime Command Matrix

Documentation HQ: [README](../README.md)

Status: `DESIGN HANDOFF` for P0-04.

This matrix maps supported operator journeys to one documented replacement
command. Wrappers remain supported while their user-facing journeys are still
needed; they must delegate process selection and startup to the canonical
runtime contracts.

| Journey | Preferred command | Compatibility wrapper | Canonical processes | Stop/recovery |
|---|---|---|---|---|
| Self-hosted Docker Compose stack | `just start` | `run_hybrid_app.bat` | `backend_app.run_api`, `backend_app.worker`, `spa-bff`, `spa-web` | `just stop`; inspect `just health` |
| Read-only Docker wrapper status | `just health` | `run_hybrid_app.bat --status` | Compose service state only; does not build, start, or open a browser | No mutation |
| Local multi-process development | `run_hybrid_app_local.bat` | Launcher UI local mode | `backend_app.run_api`, `backend_app.worker`, package dev scripts | `stop_hybrid_app_local.bat` |
| Operator UI for Docker/local selection | `run_okr_ui.bat` | `scripts/okr-launcher-ui.ps1` | Delegates to the Docker or local journey above | Use the UI Stop action or the journey-specific stop command |
| API-only development | `python -m backend_app.run_api` | None | `backend_app.run_api` | Stop the process; review API health/logs |
| Worker-only development | `python -m backend_app.worker` | None | `backend_app.worker` | Stop the process; review worker logs |
| Disposable SaaS environment provision | `just saas-provision MANIFEST=... CREDENTIAL_FILE=...` | `OKR_OPERATOR_TOKEN` plus credential file | `scripts/provision_saas_environment.py provision` | Metadata-only local adapter; repeat is idempotent |
| Disposable SaaS environment suspend | `just saas-suspend ENVIRONMENT_ID=... CREDENTIAL_FILE=...` | `OKR_OPERATOR_TOKEN` plus credential file | `scripts/provision_saas_environment.py suspend` | Metadata-only local adapter |
| Disposable SaaS environment retire | `just saas-retire ENVIRONMENT_ID=... CREDENTIAL_FILE=...` | `OKR_OPERATOR_TOKEN` plus credential file | `scripts/provision_saas_environment.py retire` | Terminal lifecycle operation |

## Boundary rules

- `just start` and `run_hybrid_app.bat` own Docker Compose selection only; they do not assemble the FastAPI application.
- `run_hybrid_app.bat --status` is a read-only wrapper path for service-state inspection and must not build, start, or open a browser.
- `run_hybrid_app_local.bat` owns local process orchestration only; application construction remains in `backend_app.main`.
- `run_okr_ui.bat` and `scripts/okr-launcher-ui.ps1` own operator interaction only.
- The root `app.py` facade is not a supported server startup command.
- Any wrapper removal requires replacement-path evidence, supported-journey confirmation, and a rollback note.
- SaaS lifecycle commands use a disposable local provider whose state file contains environment metadata only; a control plane and real provider adapter remain deferred.
- Provisioning inputs are immutable: a repeat with changed `application_version` or manifest metadata is rejected as a conflict. Use a later release-operation workflow for version changes.
- Provisioning owns environment metadata only; it must not write customer-domain records, tenant schema, RLS policy, migrations, backups, or release state.

## Evidence

- [runtime-entrypoint-contract.md](runtime-entrypoint-contract.md) defines the canonical process contracts.
- [compatibility-callers.md](compatibility-callers.md) records wrapper references and migration disposition.
- [test_hybrid_app_launcher_script.py](../tests/test_hybrid_app_launcher_script.py) covers the Windows wrapper contracts.
- `justfile` provides the canonical Compose `start`, `stop`, `health`, and quality-gate commands.
- `justfile` also provides the canonical disposable SaaS lifecycle commands: `saas-provision`, `saas-suspend`, and `saas-retire`.
