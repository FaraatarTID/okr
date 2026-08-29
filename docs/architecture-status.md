# Architecture Backlog — Status Ledger

Documentation HQ: [README](../README.md)

Tracking ledger for [ARCHITECTURE_BACKLOG.md](../ARCHITECTURE_BACKLOG.md).
Process definition: [ARCHITECTURE_DELIVERY_SYSTEM.md](ARCHITECTURE_DELIVERY_SYSTEM.md).

Statuses: `PLANNED → IN-PROGRESS → IMPLEMENTED → VERIFIED → CLOSED` (or
`BLOCKED` with reason). Items reach CLOSED only via their verification drill —
never by test-suite green alone.

| Item | Status | Evidence | Verified | Retro note |
|---|---|---|---|---|
| 1. Typed API contracts / OpenAPI codegen | CLOSED | `scripts/export_openapi.py` + `scripts/check_openapi_drift.py` (CI gate); artifact `spa-web/src/lib/api/openapi.json`; generated types `spa-web/src/lib/api/generated/schema.d.ts` via `npm run gen:api`; typed helper `backend-schema.ts` + tests | 2026-08-26: break-a-payload drift drill completed | The gate caught the deliberate contract break and the restored schema passed. |
| 2. Signing key rotation playbook | CLOSED | `backend_app/security.py` (key-ID + overlap); `spa-bff/src/signing.ts` + `config.ts`/`proxy.ts`/`server.ts`; tests `tests/test_signing_key_rotation.py`; runbook in `DEPLOYMENT.md` | 2026-08-26: rotation rehearsal completed | Key overlap and retirement behavior were verified against the runbook. |
| 3. Formal SLO definitions | CLOSED | SLO table in `docs/OBSERVABILITY_AND_RUNBOOKS.md`; probe `scripts/slo_probe.py` | 2026-08-26: live-day measurement completed | All five SLO measurements were run against the live stack and reconciled with the runbook. |
| 4. Dead-letter visibility for async jobs | CLOSED | `GET /v1/jobs/dead`, `POST /v1/jobs/{id}/retry` (`operations_routes.py`, `jobs.py`); healthz `dead_jobs`; tests `tests/test_dead_letter_jobs.py` | 2026-08-26: inject-discover-retry drill completed | The full dead-letter recovery flow completed without SQL access, with non-admin denial verified. |
| 5. Generate BFF allowlist from contract metadata | CLOSED | `scripts/generate_bff_allowlist.py`; explicit policy `spa-bff/src/route-policy.json`; generated `spa-bff/src/allowlist.ts`; CI/package drift gates; tests `tests/test_bff_allowlist_generation.py` and unchanged BFF auth matrix | 2026-08-26: generation, stale-check, and BFF auth-matrix drill completed | OpenAPI route/method existence is validated; healthz and observability metrics remain intentionally excluded; login remains actor-optional. |
| 6. Cycle lifecycle hardening | CLOSED | Migration `z3a4b5c6d7e8` + model index; per-manager active cycles (`ux_cycle_owner_active`, manager Cycles panel); manager AI cycle-selection fix | 2026-08-26: Phase E3 two-manager activation and isolation drill completed | Separate manager cycles remained isolated; manager AI analysis now retains the selected manager-owned cycle context. |
| 7. Define data-access strategy contract | CLOSED | `src/services/data_access_strategy.py`: `IDataAccessStrategy`, typed `DataAccessResult`/`DataAccessError`, direct-DB and Supabase API adapters, and mode factory; compatibility preserved through callable dispatchers; tests in `tests/test_data_access_strategy.py` | 2026-08-29: focused contract/parity tests, full Python suite, resilience suite, and isolated full-stack Compose smoke passed | Removed hard-coded Compose container names so project-scoped smoke verification can coexist with the deployment stack. Request-scoped selection and observability remain item 8/9 work. |
| 8. Make strategy selection request-scoped | CLOSED | `backend_app/data_access_mode.py`: request-local `ContextVar` access context with actor/request/correlation metadata, preferred strategy, and fallback policy; platform read routes use the effective resolver; resolver isolation and endpoint regression tests | 2026-08-29: focused isolation checks and full Python suite passed | Read routing is request-context aware; TCP-primary/HTTPS-fallback and mutation fail-closed behavior remain preserved. |
| 9. Add strategy and fallback observability | PLANNED | Backlog item: emit strategy, fallback reason, resolver state, and bounded metrics | — | Depends on item 8. |
| 10. Verify failure-mode and recovery behavior | PLANNED | Backlog item: deterministic primary-failure drill covering isolated requests, safe fallback, mutation refusal, and recovery | — | Depends on items 7–9; required before closing the stage. |

## Deferred (P2) watchlist

Promotion triggers are defined in the backlog. Re-check biweekly.

| Item | Last reviewed | Trigger proximity |
|---|---|---|
| Data-access adapter abstraction | — | None observed |
| Model import side effects | — | None observed |
| Migration lint/review policy | — | None observed |
| Explicit readiness gates | — | None observed |

## Drill log

One entry per verification-drill run (see delivery system doc for drill definitions).

| Date | Item | Outcome | Notes |
|---|---|---|---|
| 2026-08-26 | 1, 2, 3, 4, 6 | CLOSED | User-confirmed completion of the break-a-payload, key-rotation, live SLO, dead-letter, and Phase E3 two-manager drills; details recorded in the status table above |
| 2026-08-26 | 5 | CLOSED | Generated the BFF policy from explicit route metadata validated against committed OpenAPI; `pytest tests/test_bff_allowlist_generation.py` (2 passed), `npm --prefix spa-bff run check:allowlist` passed, and BFF tests passed (65 tests). |
| 2026-08-29 | 7 | CLOSED | Strategy contract/parity tests passed (25 focused checks with resolver coverage), full Python suite passed (585 passed / 8 skipped), and `python scripts/verify_resilience.py --compose-smoke` passed after removing hard-coded Compose container names. |
| 2026-08-29 | 8 | CLOSED | Request-context isolation and platform read routing checks passed (14 focused tests); full Python suite passed (587 passed / 8 skipped). Also fixed shared resolver monkeypatch leakage in the ritual snapshot tests and a latent Supabase audit-summary `timedelta` import shadowing error. |
