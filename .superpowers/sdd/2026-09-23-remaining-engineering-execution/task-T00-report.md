Documentation HQ: [README](../../../README.md)

# T00 register reconciliation — 2026-09-23

## Evidence boundary and status meaning

Source of truth: [Remaining Engineering Plan](../../../docs/REMAINING_ENGINEERING_PLAN.md), with the [execution plan](../../../docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md) used only for packet mapping and sequencing. `landed` below means implementation or a documented decision is present in this checkout; it does **not** certify merge, current remote CI, branch protection, a live drill, or release. `open` means an acceptance condition is unimplemented or unverified. `blocked` means an external fact, owner decision, target, or required fresh clone is missing. `deferred` means the register explicitly postpones the scope. A row may mention landed subsets while its overall status remains open. This reconciliation covers 55 current-register rows: 47 A–F entries and P0-1–P0-8. The latter namespace differs from historical P0-00…P0-06 in `docs/architecture-status.md`.

The working tree already had edits to `.gitignore` and `README.md`, plus the execution plan and SDD files. I preserved them. `.git` is read-only in this workspace; I made no branch, worktree, index, commit, or other Git write. Local inspection cannot establish the current state of PR #177, required CI, provider systems, a deployment drill, the configured database on the target deployment, or GitHub secrets. Historical CI/PR statements in the register remain historical, not independently verified here.

## Item-by-item reconciliation

Each source reference names the authoritative register row or progress row. Paths are relative to the repository root. Test paths identify existing targets, not tests rerun for this document-only packet.

| Item | State | Register source | Current checkout evidence and remaining acceptance |
| --- | --- | --- | --- |
| A1 | landed | Workstream A row A1; Phase 1 progress A1 | `scripts/deploy_saas_release.py` has the bootstrap guard; `tests/test_cli_entrypoint_bootstrap.py` covers the operator entrypoints. The unrelated-working-directory subprocess was not rerun. |
| A2 | landed | A row A2; Phase 1 progress A2 | `scripts/restore_saas_environment.py` has `register-target`; `src/saas/backup_operations.py` shares `validate_restore_target`; `tests/test_saas_backup_operations.py` contains the local journey. Provider-backed restoration is E1. |
| A3 | landed locally | A row A3; Phase 1 progress A3 | `.github/workflows/promote-production.yml` has `phase-1-evidence` in the promotion dependency; `tests/test_phase1_promotion_gate.py` checks placement. The real bundle in `docs/saas/phase-1-entry-evidence.md` remains blocked; remote workflow execution is unknown. |
| A4 | open | A row A4 | `backend_app/main.py` still creates `ControlPlane()` without durable operator state; `scripts/verify_process_contract.py` rejects a runtime state-path setting. `tests/test_control_plane_stateless_runtime.py` exists, but the documented lifecycle/API contradiction and its acceptance drill are not established as closed. |
| A5 | landed locally | A row A5; Phase 1 progress A5 | `scripts/attestation_verification.py` is used by `scripts/verify_recovery_evidence.py`; `tests/test_recovery_evidence.py` covers verifier behavior. This does not supply a provider signature. |
| A6 | landed locally | A row A6; Phase 1 progress A6/A6b/A6c | `.github/workflows/rollback-production.yml` passes Cosign references to the verifier; `tests/test_rollback_workflow_wiring.py` is the wiring target. `rollback-execution-verification.yml` separates post-deployment verification. Live rollback success is E3 and unknown. |
| B1 | landed locally | Workstream B row B1; Phase 1 progress B1 | `docs/saas/hamravesh-backup-onboarding.md` and `tests/test_documented_evidence_schema.py` carry the documented verifier schema. |
| B2 | open | B row B2 | `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md` still needs its remaining-work language reconciled to open repository work and linked to this register; the target edit is T05. |
| B3 | landed locally | B row B3; Phase 1 progress B3 | `docs/bff-boundary-adr.md`, `docs/security/rate-limit.json`, `docs/evidence/security-parity.json`, and `spa-bff/src/config.ts` show the corrected control/timeout distinction. D4 still owns missing BFF origin and rate-limit controls. |
| B4 | open | B row B4 | `docs/architecture/ARCHITECTURE_BACKLOG.md` now begins with a superseded warning, but retains the old active performance-probe claim at line 188 and historical tenancy execution text. The requested split/rescope is incomplete. |
| B5 | landed locally | B row B5; Phase 1 progress B5 | `.github/workflows/ci.yml:118,172` runs a named `PostgREST Exposure Gate` step under the `migration-quality` job; `ci-result` depends on `migration-quality` at `:610-629`. The old `postgrest-exposure-gate` job-ID wording in the progress row is historical. `scripts/check_rls_enabled.py` explains the PostgREST scope. Remote branch-protection wiring is unknown. |
| B6 | landed locally | B row B6; Phase 1 progress B6 | `docs/QUALITY_GATE_BASELINE.md` closes QG-001 and dates QG-002 to 2026-11-15; `scripts/check_quality_gate_baseline.py` is the local checker. The mypy debt itself remains scheduled work. |
| B7 | landed as historical cleanup | B row B7; Phase 1 progress B7 | `docs/WORKLOG.md` contains reconstructed history; the source paths named as its old unmerged set are not modified in this checkout. Current README/plan/SDD edits belong to this active execution, so the old clean-tree sentence is not a claim about today's tree. |
| B8 | landed locally | B row B8; Phase 1 progress B8 | `spa-web/src/components/atlas-shell/AdminModePanel.tsx` no longer declares the unreachable security tab; the AI sync variables and unused helper are absent from the implementation. |
| C1 | landed subset; acceptance open | Workstream C row C1; Phase 2 progress C1 and C1 note | `spa-web/src/lib/resourceCache.ts`, `cycles.ts`, `adminResources.ts`, and their focused tests implement TTL/deduplication for cycles and admin resources. Session caching was deliberately excluded to preserve fresh role checks; sign-out clears the cache. The row's literal session-cache acceptance must be read with the recorded decision, and a warmed-stack drill is still needed. |
| C2 | open | C row C2; Phase 2 progress remainder | No route-level loading/error/not-found trio or panel code split is evidenced under `spa-web/src/app`; the login page's Suspense is not the requested shell streaming. |
| C3 | open | C row C3; Phase 2 progress remainder | `docs/architecture/ARCHITECTURE_BACKLOG.md` still claims a production performance probe; no required page-load budget gate was found in `.github/workflows/ci.yml` or `justfile`. |
| C4 | landed gate; follow-up open | C row C4; Phase 2 progress C4 | `eslint.config.mjs`, root `package.json`, `spa-bff/package.json`, and `.github/workflows/ci.yml` wire lint and BFF typecheck. The register also records Node engine metadata and eight warning dispositions still pending; exact digest-pinned image runtime is unobserved. |
| C5 | open | C row C5; Phase 2 progress remainder | `PasswordChangePanel` remains reached from `spa-web/src/app/login/page.tsx`; no signed-in entrypoint was found. |
| C6 | open | C row C6; Phase 2 progress remainder | `tests/test_e2e_playwright_spa_login_to_atlas.py` remains the E2E target; the listed additional role/route journeys are not recorded as completed. |
| C7 | landed locally | C row C7; Phase 1 progress C7 | `spa-bff/vitest.config.ts` and `tsconfig.build.json` exclude compiled duplicate tests. The historical adversarial 9-file/74-test run is in the register; it was not rerun here. |
| C8 | open verification | C row C8; Phase 2 progress C8 | `spa-web/src/app/(shell)/layout.tsx`, `layout.test.tsx`, and `route-ownership.test.ts` establish one shared shell in source. The warmed-stack navigation/polling drill remains open; the current PR #177/CI state is unknown. |
| C9 | landed locally | C row C9; Phase 1 progress C9 | `spa-web/src/components/atlas-shell/useShellAccessControl.ts` and its test enforce forced password change at the shell boundary. |
| D1 | open; not started | Workstream D row D1; Phase 3 progress D1 group | `src/saas/identity_contract.py` has discovery metadata but no BFF JWKS signature gate; `src/saas/identity_ports.py` still accepts a caller-supplied `signature_valid`. |
| D2 | open; not started | D row D2; Phase 3 progress D1 group | `spa-bff/src/server.ts` and `spa-web/src/app/api/session/` contain login/me/logout, with no OIDC authorize/callback route. D2 must be integrated with D4 after D1. |
| D3 | open, with D3a landed locally | D row D3; Phase 3 progress D3a and D3 remainder | `spa-bff/test/session_revocation_replay.test.ts` covers the same-process replay fix. `spa-bff/src/session.ts` still has an in-process registry and unknown-ID active behavior; no cross-instance tri-state revocation is evidenced. D3a does not close restart, cross-instance, or unknown-session semantics. |
| D4 | open; not started | D row D4; Phase 3 progress D4 | `spa-bff/src/server.ts` has an `onRequest` hook but no origin/rate-limit enforcement for session routes; `spa-bff/test/csrf_rejection.test.ts` covers an existing catch-all CSRF branch only. Coupled to D2. |
| D5 | open; not started (scheduling deferred) | D row D5; Phase 3 progress D1 group | `src/saas/identity_ports.py` remains test-port infrastructure and `src/saas/entitlement_policy.py` remains disabled. A concrete customer requirement and owner must trigger implementation. |
| D6 | open implementation; decision landed | D row D6; Phase 3 progress D6 | `src/saas/identity_contract.py` still defines the Python token pair and `spa-bff/src/session.ts` defines the BFF authority with incompatible shape. The BFF-owner decision is documented; external-consumer search and explicit deprecation/rejection acceptance remain. |
| D7 | open; not started | D row D7; Phase 3 progress D1 group | `spa-bff/src/server.ts` forwards cookie-frozen `x-okr-token-version`; `backend_app/security.py` does not establish next-proxied-request invalidation across protected routes. D10 is the related enforcement breadth. |
| D8 | blocked on chosen integration/target contract | D row D8; Phase 3 progress D8 | Historical read-only database counts in the register refuted `username == email`; they do not describe the current target deployment. Locally, `src/models.py:125-155` defines `User` without an external-subject/email link, and `backend_app/routers/platform_routes.py:131-153` still resolves `/v1/auth/me` by `User.username == actor`. A search of `alembic/versions/` and `backend_app/routers/` for `external_subject`, `enterprise_exchange`, and OIDC exchange routes found no migration or backend exchange. Target provisioning cannot be rechecked locally. |
| D9 | blocked on IdP fact; implementation open | D row D9; Phase 3 progress D9 | `src/saas/identity_contract.py` carries `email_verified` without enforcing true, and no production IdP guarantee is locally available. |
| D10 | open | Phase 3 progress D10 (no original D issue row) | `spa-bff/test/token_version.test.ts` pins forwarding, while `backend_app/routers/platform_routes.py` and `ai_routes.py` are the only recorded consumers; no full protected-route version-bump matrix is evidenced. |
| E1 | blocked | Workstream E row E1 | `src/saas/backup_operations.py` local provider cannot substitute for selected provider/API and provider-issued IDs. `docs/saas/phase-1-entry-evidence.md` says `UNSELECTED`. |
| E2 | blocked | E row E2 | `src/saas/release_operations.py:106-123` defines the `RuntimeAdapter` protocol and `LocalRuntimeAdapter`, whose docstring says it never changes a live service. `scripts/deploy_saas_release.py:16,78` imports and constructs that local adapter. A search for `RuntimeAdapter` implementations under `src/saas/` found no live adapter; a real target and its contract are unavailable. |
| E3 | blocked, code remainder open | E row E3 | `rollback-execution-verification.yml` exists, but operator-supplied execution outcome and paired live rollback evidence are unavailable. The register's strict execution-record path remains a separate acceptance check. |
| E4 | deferred | E row E4 | `deploy/k8s/deployment-backend-api.yaml` and `deployment-backend-worker.yaml` retain `REPLACE_WITH_RELEASE_DIGEST`; SPA/BFF target inputs are absent. |
| E5 | blocked | E row E5 | `docs/saas/phase-1-entry-evidence.md` and `release-signoff.md` still say `UNASSIGNED`, `UNSELECTED`, and `real_data_approval: false`. |
| E6 | deferred | E row E6 | Phase 3 operations scope is explicitly deferred in the register. |
| F1 | open, guard landed | Workstream F row F1 | `backend_app/read_query_helpers.py` has `_validate_read_scope`; F3/F4 row fixes are in `src/services/supabase_api_mode_read.py`. The row itself says one non-admin TCP/HTTPS payload-level parity check across all six kinds is not yet met. |
| F2 | open | F row F2 | `src/crud_query_helpers.py` now refuses an actorless `get_node` unless explicitly allowed; `tests/test_crud_authorization.py` covers the helper. The BFF-to-backend actor-presence surface for all named kinds remains unaudited. |
| F3 | landed locally | F row F3 | `backend_app/read_query_helpers.py` applies HTTPS cycle row scope; `src/services/supabase_api_mode_read.py` has the goal filters; `tests/test_supabase_api_mode_read.py` covers needing-checkin and retro-window cases. This records specific fixes, while F1's combined parity acceptance stays open. |
| F4 | landed locally | F row F4 | `src/services/supabase_api_mode_read.py` uses `_allowed_goal_ids_for_cycle` for the two by-cycle queries; focused Supabase read tests exist. |
| F5 | blocked | Phase 2 progress F5 (not a Workstream F issue row) | `spa-bff/package.json` still declares `^5.6.1`; root and BFF lockfiles pin `fastify` 5.8.5. The historical stale-resolution failure requires a genuine fresh full clone, which this read-only-Git workspace cannot supply. No new advisory/version assertion is made. |
| F6 | blocked external evidence; wiring landed | Phase 2 progress F6 (not a Workstream F issue row) | `scripts/check_saas_phase1_evidence.py` is in promotion workflow through A3, while `docs/saas/phase-1-entry-evidence.md` remains blocked. Real provider records, owners, approval, and measured objectives are absent. |
| F7 | landed as historical local repair | Phase 2 progress F7 (not a Workstream F issue row) | `spa-web` has its typecheck script and the CI workflow has a SPA Web typecheck step. Current generated `.next` state and remote CI were not reverified. |
| F8 | open | Phase 2 progress F8 (not a Workstream F issue row) | `scripts/verify_observability_readiness.py` and `scripts/verify_release_pair.py` exist but are not invoked by `.github/workflows/`, `justfile`, or `.pre-commit-config.yaml`; the full 25/14 inventory is historical and needs T07's classification and wiring evidence. |

### Current-register P0 progress items

These are the active P0-1–P0-8 rows under Phase 1 Progress in the authoritative register, not the historical architecture ledger's P0-00…P0-06 packages.

| Item | State | Register source | Current checkout evidence and remaining acceptance |
| --- | --- | --- | --- |
| P0-1 | landed locally; historical measurement | Phase 1 Progress row P0-1 | `backend_app/scope_resolution.py:17-26` has the request-scoped `ContextVar` cache; `backend_app/security.py:174-176` resets it. `tests/test_read_path_budget.py` measures statements and connections, and `tests/test_read_path_budget_postgres.py` contains the PostgreSQL harness. The row's measured figures are historical test evidence, not a current production wall-clock measurement. |
| P0-2 | open | Phase 1 Progress row P0-2 | `backend_app/response_scope_helpers.py:469-494` admits tasks by `assignee_id` and can skip a row on an exception; `src/services/supabase_api_mode_read.py:569-584` narrows `tasks.by_cycle` through allowed owning goal IDs. The two paths still lack the same visibility predicate and a parity check. |
| P0-3 | open | Phase 1 Progress row P0-3 | `backend_app/read_query_helpers.py:386-490` fans out `ritual.snapshot`; `tests/test_read_path_budget.py:480-486` explicitly leaves that kind unbudgeted because its SQLite fixture cannot run `fn_ritual_snapshot`. A PostgreSQL ritual snapshot budget is still required; P0-1's cache cannot be assumed to close it. |
| P0-4 | open verification; repository wiring landed | Phase 1 Progress row P0-4 | `deploy/nginx.conf`, `spa-web/src/lib/bff-proxy.ts`, `spa-bff/src/proxy.ts`, and `backend_app/security.py` carry the private `X-OKR-Client-IP` hop contract; `tests/test_rate_limit_key_trust.py`, `tests/test_login_throttle_key.py`, and `spa-bff/test/forwarded_ip.test.ts` cover other hops. `spa-web/src/lib/bff-proxy.test.ts` has five logging cases and no SPA→BFF forwarding case. The deployed edge-only ingress property cannot be proven locally. |
| P0-5 | open only for callerless identity controls | Phase 1 Progress row P0-5 | `spa-bff/src/session.ts:136` exports `revokeSessionsForIdentity`, referenced by `spa-bff/test/identity_session_revocation.test.ts` but no `spa-bff/src` caller. `src/saas/identity_ports.py` is imported in `tests/test_saas_identity_ports.py`, with no importer found under `src/`, `backend_app/`, or `scripts/`. The row records the other sweep members as closed; no exhaustive new audit or remote CI assertion is inferred. |
| P0-6 | landed locally; historical proof | Phase 1 Progress row P0-6 | `backend_app/schemas.py:645-655` no longer accepts login-body `client_ip`; `backend_app/routers/platform_routes.py:78-90` derives it from trusted request state. `tests/test_login_throttle_key.py` has the positive throttle-row and attacker-address rejection cases. The row's original HTTP exploit reproduction is historical evidence and does not itself verify deployment. |
| P0-7 | landed locally; historical proof | Phase 1 Progress row P0-7 | `tests/test_performance_hotpaths.py:435-443,499` documents removal of ineffective module-attribute dependency patches; `backend_app/routers/platform_routes.py` binds `Depends(main.require_service_access)` at route construction. The fix removes a misleading test idiom; it does not establish new auth-matrix coverage. |
| P0-8 | open; PgBouncer evidence required | Phase 1 Progress row P0-8 | `src/database.py:147-178` keeps PostgreSQL `NullPool` by default and leaves app pooling opt-in via `OKR_DB_USE_NULL_POOL=false`. `tests/test_read_path_budget_postgres.py:225-308` exercises direct PostgreSQL and explicitly says it does not verify transaction-pool PgBouncer. A pooler-backed read-path run and recorded result are required before changing the default. |

The register also has **Phase 2 progress F1–F4** entries for retry timeout, BFF proxy logging, lint warning triage, and the Windows npm scan launcher. They are distinct from **Workstream F rows F1–F4** above. The former record landed code at `spa-web/src/lib/api/http.ts`, `spa-web/src/lib/bff-proxy.ts`, the ESLint targets, and `scripts/verify_dependency_scans.py`; they are not substitutes for read-path authorization acceptance. This duplicate numbering should be disambiguated in a future register edit without erasing either history.

## Correction made to the authoritative register

The Workstream F preface still said all six cycle-scoped kinds leak over HTTPS and F3 is open, while row F3 records those individual fixes as closed. I changed only that stale preface. It now distinguishes the landed F3 filters from F1's still-open combined payload parity check. No acceptance contract, row history, or status table was deleted.

## Evidence and verification limits

Local focused targets relevant to later packets include `tests/test_phase1_promotion_gate.py`, `tests/test_rollback_workflow_wiring.py`, `tests/test_documented_evidence_schema.py`, `tests/test_control_plane_stateless_runtime.py`, `tests/test_supabase_api_mode_read.py`, `tests/test_crud_authorization.py`, `tests/test_read_path_budget.py`, `tests/test_read_path_budget_postgres.py`, `tests/test_login_throttle_key.py`, `spa-bff/test/session_revocation_replay.test.ts`, `spa-bff/test/token_version.test.ts`, `spa-web/src/lib/resourceCache.test.ts`, and `spa-web/src/app/route-ownership.test.ts`. This packet changed prose only, so no behavioral tests were run. The exact doc/status checks and output are recorded below after execution.

External unknowns: current remote CI/required-check results; PR #177 merge or review state; current advisory registry and a fresh clone for F5; deployment/runtime topology and edge-only BFF ingress; PgBouncer transaction-pool behavior; provider backup/restore IDs, measured RPO/RTO, rollback rehearsal, target database provisioning, IdP claim guarantees, operations owner, and real-data approval. None was inferred from commit subjects or the execution plan.

## Commands run for T00

From `C:\Faraatar-TID_Apps\okr`:

| Command | Exit | Exact relevant output |
| --- | ---: | --- |
| `python scripts/check_docs_hq_links.py` | 0 | `Documentation HQ link check passed (91 markdown files scanned).` |
| `python scripts/check_quality_gate_baseline.py` | 0 | `Quality baseline review date: 2026-09-23`; `- QG-002: expires 2026-11-15 | Repo-wide mypy remains staged; broad default coverage is active for scripts plus the runtime-core backend_app modules. Measured 2026-09-20: 127 errors in 24 of 347 checked files (src 10, tests 10, backend_app 2, scripts 2), led by arg-type 56, union-attr 16 and attr-defined 15.`; `Quality baseline check passed.` |
| `git diff -- docs/REMAINING_ENGINEERING_PLAN.md` | 0 | One prose hunk: the stale F3-open preface is replaced; all table rows and acceptance contracts are unchanged. |
| `git status --short` | 0 | `M .gitignore`; `M README.md`; `M docs/REMAINING_ENGINEERING_PLAN.md`; `?? .superpowers/sdd/2026-09-23-remaining-engineering-execution/`; `?? docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md`. Git also warned that the user's global ignore file was inaccessible; that warning does not affect the observed tracked diff. |
| `git diff --check` | 1 | Existing unrelated `.gitignore:110: new blank line at EOF.` Git also warned that its working-copy CRLF would be replaced by LF. `.gitignore` was already modified before T00 and was not changed here. |
| `git diff --check -- docs/REMAINING_ENGINEERING_PLAN.md` | 0 | No output. |
| Report formatting check (`python -c`, byte/count inspection) | 0 | `report rows: 47`; `CR: 0 LF: 88 final newline: True`; `trailing whitespace lines: []`. |

No behavioral tests, remote CI queries, Git writes, or provider operations were performed for this document reconciliation.

## Review fix, round 1

- D5 now says **open; not started**, while retaining the customer requirement and owner as the scheduling trigger. This matches the Phase 3 progress row.
- D8 now cites `src/models.py:125-155`, `backend_app/routers/platform_routes.py:131-153`, and the inspected `alembic/versions/` plus `backend_app/routers/` search scope. The database counts remain historical; current target provisioning is unknown.
- E2 now cites `src/saas/release_operations.py:106-123` and `scripts/deploy_saas_release.py:16,78`, plus the `src/saas/` implementation search. No other register scope changed in this fix round.

Commands rerun from `C:\Faraatar-TID_Apps\okr` after those three row edits:

```text
> python scripts/check_docs_hq_links.py
Documentation HQ link check passed (91 markdown files scanned).
Exit code: 0

> python scripts/check_quality_gate_baseline.py
Quality baseline review date: 2026-09-23
- QG-002: expires 2026-11-15 | Repo-wide mypy remains staged; broad default coverage is active for scripts plus the runtime-core backend_app modules. Measured 2026-09-20: 127 errors in 24 of 347 checked files (src 10, tests 10, backend_app 2, scripts 2), led by arg-type 56, union-attr 16 and attr-defined 15.
Quality baseline check passed.
Exit code: 0
```

## Accepted T01 audit reconciliation, round 2

The Phase 1 Progress table also contains eight active P0-1–P0-8 rows. They are now reconciled above, bringing this report to 55 current-register items. P0-1, P0-6, and P0-7 retain historical/local completion claims with their measurement or coverage limits; P0-2, P0-3, P0-4, P0-5, and P0-8 retain their specific open acceptance conditions. The T00 brief now includes this namespace. The register's status-tracking instruction now keeps current A–F/P0 status here and preserves `docs/architecture-status.md` as the historical P0-00…P0-06 ledger. B5's report evidence now describes the current named CI step under `migration-quality`; the old job-ID wording is identified as historical. No execution-plan packet mapping was edited.

Commands run from `C:\Faraatar-TID_Apps\okr` after those edits (the `Exit code` lines record command status and are not checker stdout):

```text
> python scripts/check_docs_hq_links.py
Documentation HQ link check passed (91 markdown files scanned).
Exit code: 0

> python scripts/check_quality_gate_baseline.py
Quality baseline review date: 2026-09-23
- QG-002: expires 2026-11-15 | Repo-wide mypy remains staged; broad default coverage is active for scripts plus the runtime-core backend_app modules. Measured 2026-09-20: 127 errors in 24 of 347 checked files (src 10, tests 10, backend_app 2, scripts 2), led by arg-type 56, union-attr 16 and attr-defined 15.
Quality baseline check passed.
Exit code: 0

> git diff --check -- docs/REMAINING_ENGINEERING_PLAN.md
(no output)
Exit code: 0

> python -c "...report row/format inspection..."
A-F rows: 47
P0 rows: 8
CR: 0 final newline: True trailing whitespace lines: []
Exit code: 0
```

## Blocking cross-signoff correction, round 3

The canonical register's Assumptions paragraph still said that the four most
recent commits covered an OIDC flow and stateless logout revocation. This
contradicted its own D2 row and Phase 3 `D1, D2, D5, D7 | Not started` row.
Checkout inspection found only `/session/login`, `/session/me`, and
`/session/logout` in `spa-bff/src/server.ts`, with matching login/me/logout
passthroughs under `spa-web/src/app/api/session/` and no OIDC
authorize/callback routes. `git log -4 --format='%h %s'` showed two docs/status
commits (`0c29741`, `7dc7403`), a twelve-factor test commit (`52102c2`),
and a P0-5 test commit (`c086e55`), not an OIDC flow. D3a's progress row also
explicitly limits its landed correction to same-process replay and leaves
restart, cross-instance, and unknown-session behavior open. The Assumptions
paragraph now states those bounds and retains only B7's historical disposition
and the requirement to commit or park current working-tree work.

The D4 implementation note separately proposed `request.ip` because
`trustProxy` is enabled. `docs/client-ip-trust-adr.md:38-63` establishes a
private, edge-overwritten `X-OKR-Client-IP` and forbids XFF/X-Real-IP as trust
inputs; `spa-bff/src/server.ts` currently sets `trustProxy: true`, and
`spa-bff/src/proxy.ts:105-117` forwards the private header. The canonical
note now keys a future BFF throughput limiter on the private header, falling
back only to the raw immediate socket peer when absent. It excludes
proxy-derived `request.ip`, `X-Forwarded-For`, and `X-Real-IP`, and preserves
the login lockout's different absent-header rule. Packet T24 and its plan and
ledger self-scans now require behavioral limiter-key cases. T31 still owns
actual edge overwrite and deployed BFF reachability proof.

These were documentation and execution-contract corrections. No application
code or behavioral tests changed; T00/T01 cross-signoff remains pending scoped
independent review.

Round-3 checks from `C:\Faraatar-TID_Apps\okr`: `python
scripts/check_docs_hq_links.py` passed (91 markdown files); `python
scripts/check_quality_gate_baseline.py` passed (QG-002 expires 2026-11-15);
`git diff --check -- docs/REMAINING_ENGINEERING_PLAN.md` passed. A UTF-8
format scan of the canonical register, execution plan, this report, and the
progress ledger found final LF newlines, no CR bytes, and no trailing
whitespace. Fenced blocks in this report and the register were inspected
separately. These checks do not prove the future D4 limiter behavior; T24
must add behavioral cases for trusted private-header presence, absent-header
raw-peer fallback, conflicting caller-supplied XFF/X-Real-IP, and the
separate login-lockout absent-header rule.
