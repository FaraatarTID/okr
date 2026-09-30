# Deployment Operations Guide (Compatibility Redirect)
Documentation HQ: [README](../README.md)

This document was consolidated to reduce overlap across deployment docs.

Canonical references (EN):
- Enterprise deployment playbook: [../DEPLOYMENT.md](../DEPLOYMENT.md)
- Runtime policy and env keys: [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)
- Incident and troubleshooting: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Production operations observability and incident runbooks: [OBSERVABILITY_AND_RUNBOOKS.md](OBSERVABILITY_AND_RUNBOOKS.md)
- Retention/backup/recovery readiness and OPS-01 execution evidence: [OPS_READINESS_AND_RECOVERY_GUIDE.md](OPS_READINESS_AND_RECOVERY_GUIDE.md)

## Runtime logging and disposability contract

The API, worker, and BFF write structured JSON lifecycle and error events to
stdout or stderr. The audit and error helpers use process stream handlers only;
they do not create or write operational log files. Events include an event name
and UTC timestamp; request events carry correlation/request identifiers where
available.

Operational logs are metadata-only. Audit events are also persisted in the
database for application audit queries; this durable audit record is separate
from operational log transport. Never log request headers, cookies, request
bodies, passwords, authorization values, service tokens, or signing/session
secrets. Error events use error type/code and sanitized context instead of raw
credentials.

Run the repository gate before release:

```text
python scripts/verify_logging_contract.py
```

The process model is disposable: health checks and orchestrator restart behavior
must be able to replace API, worker, and BFF processes without relying on local
process state. Durable state belongs in configured backing services.

## Release and runtime contract

The canonical versioned runtime contract is `deploy/runtime-matrix.json`. Run
`python scripts/verify_runtime_matrix.py` and
`python scripts/check_immutable_deploy_config.py` before publishing or promoting
a release. Production and staging must consume the same digest-pinned manifest;
provider differences are limited to injected configuration, networking, and
explicit resource sizing.

The PostgreSQL integration verifier selects a free localhost port when its
preferred port is occupied and removes only its temporary `postgres` service.
It does not remove unrelated services from the Compose project. Migration
execution remains an explicit one-off operation (`uv run alembic upgrade head`)
and production backup/restore evidence is maintained separately from disposable
local verification.

## Schema provenance

The database schema must come from `alembic upgrade head`, never from hand-written
SQL in a dashboard editor. A hand-built database drifts silently: the demo Supabase
project once carried uppercase `userrole`/`taskstatus` labels, `varchar` columns where
the migrations create enum types, and no `ux_cycle_owner_active` index, while
`alembic_version` still claimed it was current. `OKR_DATA_ACCESS_MODE=database` then
crashed at startup with `LookupError: 'ADMIN' is not among the defined enum values`.

- Startup now runs `src/schema_guard.py` after the migrations. If a live PostgreSQL
  enum lacks a label the models write, the backend refuses to start with one message
  naming the enum, the labels present and the labels needed.
- The fix is to rebuild on an empty schema, not to rename labels in place. Back up the
  rows, drop the application tables and enum types, run `alembic upgrade head`, and
  restore the rows with the lowercase labels.
- The `backend_*` tables (nonce, rate limit, distributed state, idempotency) are not in
  the migrations. `backend_app/security_state.py` creates them on first use with row
  level security enabled and no `anon`/`authenticated` grants.
- `supabase_api` mode writes uppercase role labels (`_role_for_storage`), so it does not
  work against a schema built by the migrations. It is alpha/self-hosted compatibility
  only; customer deployments use `database` mode.
- `fn_activate_cycle` and `fn_ritual_snapshot` are Supabase RPC functions used only by
  `supabase_api` mode. They are not part of the baseline migration, so a rebuilt schema
  does not have them.
- On the rebuilt demo database, tables created by the `okr_app` role carried no grants
  for `anon`, `authenticated` or `service_role`, so PostgREST (and therefore
  `supabase_api` mode) cannot read them. After any rebuild, run
  `python scripts/check_rls_enabled.py` against the database to confirm row level
  security is on and the PostgREST roles hold no grants.
