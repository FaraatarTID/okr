# Remaining Engineering Work — Multi-Agent Execution Plan

Documentation HQ: [README](../../../README.md)

**Status:** ACTIVE execution plan; subordinate to the authoritative [Remaining Engineering Plan](../../../docs/REMAINING_ENGINEERING_PLAN.md).

> **For agentic workers:** Use `superpowers:subagent-driven-development` for task-by-task execution. Use `superpowers:executing-plans` only for a task that cannot be delegated safely. If the required Superpowers workflow is unavailable, stop and report that prerequisite; do not silently substitute another process.

## Goal and Source of Truth

Complete repository work that remains open in `docs/REMAINING_ENGINEERING_PLAN.md`, with independent acceptance evidence and explicit owner gates for decisions or evidence agents cannot supply. This plan adds execution boundaries and integration order; it does not create a second status register or override the canonical acceptance criteria.

The register's Phase 1 P0-1…P0-8 and A–F progress tables are authoritative. **D1, D2, D5, and D7 are not started**. D3a closes only a same-process replay defect; restart and cross-instance revocation, unknown-session fail-closed behavior, and durable revocation remain open. No packet may describe OIDC login as shipped.

## Execution Model

- **Exact packet count: 36.** Packets are `T00` through `T35`, unique and contiguous; the register-item mapping is below. These IDs are intentionally distinct from register IDs such as D1 and P0-1. The steward ruled for four separately reviewable P0 packets (T32–T35); the cost if this split is wrong is extra coordination and packet bookkeeping.
- Assign one implementer per packet. Use a dedicated branch/worktree when Git writes are available; in the current managed checkout `.git` is read-only, so use serial file ownership, snapshots, task reports, and independent reviews without attempting Git writes. The integration steward serializes shared OpenAPI, allowlist, workflow, and dependency-lockfile edits. A second reviewer independently verifies T00 against the register before implementation assignments begin.
- Run multiple agents only on packets with disjoint files and no shared contract in flight. Dependencies below are hard gates, not suggestions. Agent count does not override integration order.
- Before dispatch, compare each packet to the current register, including the P0 map below; verify its self-consistency row and the unique, contiguous T00–T35 set. Record the source row, exact files owned, focused tests, changed contracts, acceptance evidence, and blocked trigger in the SDD progress ledger at `.superpowers/sdd/2026-09-23-remaining-engineering-execution/progress.md`. Reserve files before assigning T08–T10, whose directory scopes overlap other packets.
- Keep current A–F status in `REMAINING_ENGINEERING_PLAN.md`; keep `docs/architecture-status.md` in its historical P0-00…P0-06 namespace. Do not add current A–F items there or rely on the gitignored worklog as shared agent state.
- Dependency changes are serialized. T06 must use a genuine fresh clone, not a Git worktree sharing the current repository's common Git directory. No other packet edits either npm lockfile until T06 is integrated; later dependency additions are handled by the integration steward in a separate lockfile pass.
- Any packet adding or changing a backend API route reserves the shared contract lane and performs this sequence once, after implementation: `uv run python scripts/export_openapi.py`; `npm --prefix spa-web run gen:api`; `npm --prefix spa-bff run gen:api`; update `spa-bff/src/route-policy.json`; `uv run python scripts/generate_bff_allowlist.py`; run generated-artifact and mutation-auth-matrix checks. Do not let parallel agents regenerate or hand-edit these shared artifacts.

## Ordered Waves and Task Packets

### Wave 0 — Reconcile the baseline

| Packet | Register scope | Work and exit condition |
|---|---|---|
| **T00 — Register reconciliation** | P0-1…P0-8; A1–A6, B1–B8, C1–C9, D1–D10, E1–E6, F1–F8 | Compare all 55 current rows and progress notes against the checkout and available CI/PR evidence. Record `landed`, `open`, `blocked`, or `deferred` with source and evidence. Carry P0-1/P0-6/P0-7 as closed baseline history, qualifying P0-1's SQLite versus PostgreSQL evidence and P0-6's P0-4 trust dependency. Keep P0-2/P0-3/P0-5/P0-8 open and P0-4 repository-complete but deployed edge unverified. Mark D1, D2, D5, D7 not started absent fresh evidence; D3a is the same-process subset only. For B5, current `ci-result` depends on `migration-quality`, which contains the PostgREST Exposure Gate step; the former `postgrest-exposure-gate` job name is historical. Do not infer remote branch protection or completion from commit subjects or this plan. |
| **T01 — Independent baseline audit** | Same 55 rows as T00, packet map and conflict matrix | A second reviewer checks T00 against all register progress tables, including P0-1…P0-8, especially D1–D10 and F5–F8. Verify all 36 unique, contiguous packet IDs, P0 and A–F mapping, each self-consistency row, shared-file conflicts, and D1/D2+D4 ordering. T00 is not accepted until discrepancies are reconciled and both reviewers sign off in the SDD ledger. |

### Wave 1 — Authorization, integrity, documentation, and quality

| Packet | Register scope | Work and exit condition |
|---|---|---|
| **T02 — Read-path payload parity** | F1, P0-2; verify F3 closure | Decide and document the intended task visibility predicate **before changing code**. Compare TCP `backend_app/response_scope_helpers.py:469-494` with HTTPS `src/services/supabase_api_mode_read.py:564-650` for owner-visible and assignee-visible tasks, including an in-scope assignee on an out-of-scope goal. Remove the broad `except Exception: continue` silent row loss; injected task attribute/query failures must produce an explicit error or bounded documented outcome. Complete six-kind restricted non-admin payload parity in `tests/test_dual_mode_parity.py`, preserving F3's closed filters and a negative case for each removed filter. Serialize with T03 if actor presence affects the same paths. |
| **T03 — Actor-presence audit** | F2 | Trace all seven read kinds enumerated in the register through BFF, backend, and `get_node`; prove actor presence at each boundary or enforce rejection end to end. Tests demonstrate that actorless requests cannot reach protected reads. Serialize shared read-path changes with T02 and T32. |
| **T04 — Evidence gate verification and disposition** | A3 Done; F6 external evidence gate | Refresh the existing A3 placement and fixture-wiring evidence: `.github/workflows/promote-production.yml` already runs `scripts/check_saas_phase1_evidence.py` in `phase-1-evidence`, required by the production approval job; `.github/workflows/ci.yml` runs the full pytest fixture suite, and `tests/test_phase1_promotion_gate.py` pins promotion placement and the absence of the real-bundle gate from PR CI. Verify these contracts and record that no repository wiring gap remains when they hold. F6 remains blocked on genuine provider-issued records, measured RPO/RTO, attestation, named owners and real-data approval; do not fabricate or insert those facts. If an A3 contract has regressed, report the exact mismatch and seek a scoped plan update before code changes. Do not duplicate the existing gate or require the real bundle on ordinary PRs. |
| **T05 — Roadmap and backlog truth** | B2, B4 | Correct roadmap claims to separate repository implementation from external evidence. Split/relabel the old architecture backlog so rejected tenancy scope is historical and any retained performance work points to the current plan. Preserve ADR-001 and current-plan links. |
| **T06 — Fastify advisory and lockfile repair** | F5 | Work from a fresh full clone. Re-check the advisory at execution time, select a supported non-vulnerable Fastify release, regenerate lockfiles through npm, and verify with `npm ci`, workspace tests/build/typecheck, and audit. Verify the result again from an unrelated clean clone. If the same stale-resolution failure recurs, stop and report the exact reproduction; do not edit lockfile internals by hand or retry the same environment. |
| **T07 — Script enforcement inventory** | F8 | Classify every listed script as CI gate, operator command, imported helper, or dead code. Wire only deterministic repository checks to CI/`just`; keep real-provider checks in release/operations; remove a script only after confirming no callers. Invoke package scripts as `python -m scripts.X`, never `python scripts/X.py`. Every wired checker needs a positive and negative fixture and a wiring test proving the workflow executes it. |
| **T08 — Mypy burn-down: backend app** | QG-002 | Reduce errors in the assigned `backend_app` files; do not touch shared generated artifacts. Record the exact `--no-incremental` count and focused tests. |
| **T09 — Mypy burn-down: runtime core** | QG-002 | Reduce errors in the assigned `src` files with the same count and evidence rules as T08. |
| **T10 — Mypy burn-down: tests and scripts** | QG-002 | Reduce errors in assigned `tests` and `scripts`; preserve meaningful typing rather than broad suppressions. Integrate the three disjoint packets and meet the existing ≤80 / ≤40 / zero milestones by 2026-10-15 / 2026-11-15 / 2026-12-31. |

### Wave 2 — Frontend performance and quality

| Packet | Register scope | Work and exit condition |
|---|---|---|
| **T11 — Cache and shared-shell verification** | C1, C8 | Refresh current PR/commit state first. Verify TTL, in-flight de-duplication, mutation invalidation, role freshness, sign-out clearing, and warmed-stack navigation. Do not add session caching; the register records that choice. Do not mark C8 verified until its shell/polling drill passes. |
| **T12 — Route streaming and code-splitting** | C2 | Add route loading/error/not-found handling and split mode panels. Preserve login redirects, admin gating, forced-password-change flow, and deep-link bootstrap. The fallback must not flash authenticated chrome before access checks resolve. |
| **T13 — Frontend performance budget** | C3 | Add the deterministic request-waterfall check to PR CI and a pinned-condition warmed-stack budget probe to release evidence. Pin browser, stack readiness, and measurement inputs; do not gate PRs on noisy wall-clock timing. Reconcile `docs/architecture/ARCHITECTURE_BACKLOG.md` probe claims with T05. P0-3 and P0-8 belong to T32 and T35, not this browser budget. |
| **T14 — In-app password change** | C5 | Add a signed-in entry point and success/failure tests; no sign-out should be required to change the password. |
| **T15 — Frontend route E2E** | C6 | Visit each non-admin route as admin, manager, and member with route-specific UI assertions. Admin completes users/teams/backup/audit; managers retain Cycles-only access; members are denied Admin on direct visit, not merely hidden from its navigation. Verify alignment and RTL in rendered UI states (they are not routes), keep test data isolated, and assert deep-link state after direct load. |
| **T16 — Runtime version and lint findings** | C4 | First inspect the exact Node version in the digest-pinned BFF image and the CI runtime. Only then align `engines.node`; if the image version cannot be observed, leave the declaration unchanged and keep the mismatch open. Resolve remaining lint findings by wiring behavior only when a documented supported flow requires it; otherwise remove dead code. Do not silence findings solely to reach zero warnings. |

### Wave 3 — Enterprise identity

Register-to-packet mapping: **D1→T18; D2→T24; D3→T22–T23; D4→T24; D5→T25; D6→T17; D7/D10→T21; D8→T19; D9→T20.** P0-5's two callerless controls have their own T34 disposition after the identity design packets.

| Packet | Register scope | Work and exit condition |
|---|---|---|
| **T17 — Single session authority** | D6 | Search for external consumers of the Python token format. Deprecate the Python issuer/verifier and prove the BFF rejects Python-issued tokens. Delete the old pair only if the consumer search finds none; otherwise keep it explicitly non-authoritative and document the compatibility bound. |
| **T18 — ID-token verification gate** | D1 | Implement verification with an audited JOSE library before trusting claims: JWKS key selection, only RS256/ES256/PS256, exact issuer and audience, expiry/issued-at within 60-second skew, constant-time nonce comparison, TTL cache and one bounded JWKS refresh for unknown `kid`. Reject `none`, all `HS*`, and invalid signatures. No real login route is enabled until this packet passes. |
| **T19 — Provisioned identity resolution** | D8 | **Before production integration implementation**, recount provisioned usernames/email shapes and identity-link uniqueness and confirm the invariant on the target deployment; the historical one-row database count is not current target evidence. Fixture/design preparation may precede the recount, but migration, backfill, and production exchange integration stay blocked if target facts or authorized linking are unavailable. Use a verified issuer/subject link to an existing provisioned user; never infer `username == email` or create users just in time. Resolve the migration freeze and explicitly authorized bootstrap/backfill path, then add the selected backend exchange and full OpenAPI/route-policy/allowlist/auth-matrix chain. Unlinked or ambiguous accounts fail closed. |
| **T20 — Verified-email contract** | D9 | Require `email_verified === true`; missing, false, or non-boolean claims mint no session. The identity owner must confirm the selected IdP guarantees this claim for legitimate accounts. If that fact is unavailable, keep production login blocked; do not add an email-based fallback. |
| **T21 — Token-version enforcement** | D7, D10 | Enforce the user-selected next-proxied-request revocation bound across every protected route, not only `/auth/me` and selected AI routes. Test a version bump against the full protected route matrix and document that this revokes all of an account's sessions. |
| **T22 — D3 architecture decision** | D3 | Before implementation, compare the register's two options: account-wide `token_version` revocation versus a per-session shared revocation registry. Record whether D3's requirements can change. `token_version` alone cannot be claimed to satisfy unknown-`sid` rejection or per-session revocation unless the acceptance contract is explicitly revised and approved by the security/product owner. No implementer chooses this tradeoff. |
| **T23 — Implement approved D3 design** | D3 | Start only after T22 owner approval. If per-session semantics remain required, use a backend-owned durable store behind a signed BFF-to-backend API, with `active`/`revoked`/`unavailable` results; unknown IDs reject and unavailable returns 503. Preserve admin+CSRF deprovision and signed service-to-service contract where required. If the owner approves account-wide semantics instead, implement only the approved `token_version` path and revise acceptance docs. Include a bounded cutover that deliberately reauthenticates legacy sessions rather than trusting unknown IDs. Coordinate `spa-bff/src/session.ts`, `spa-bff/src/server.ts`, backend identity responses, generated session schema, and async callers with T18–T20/T24. |
| **T24 — Coupled D4 + D2 integration unit** | D2, D4 | **One indivisible integration, review, and release unit** (one branch/merge when Git writes are available). Start after T18 and T33, with D6/D8/D9 contracts reconciled. Implement BFF authorize/callback and SPA passthroughs together with route/method-specific origin validation, CSRF policy, and general/auth rate-limit hooks. Key the BFF throughput limiter on the private `X-OKR-Client-IP`, falling back to the raw immediate socket peer only when that header is absent; proxy-derived `request.ip`, `X-Forwarded-For`, and `X-Real-IP` must not supply client identity. Test conflicting caller-supplied `X-Forwarded-For`/`X-Real-IP`, trusted-header presence, and the absent-header aggregate peer limit; retain the login lockout's distinct no-IP fallback. Preserve the browser's `Origin` through the SPA proxy for BFF validation on browser-initiated POST login, POST authorize initiation, logout, and authenticated writes; compare it with the exact configured public SPA origin. The OIDC callback is a cross-site top-level GET: it is the narrow exception to Origin comparison, admitted only at the fixed public redirect URI with a valid `HttpOnly` + `SameSite=Lax` browser-bound transaction cookie, single-use state, nonce, and PKCE S256. Keep its rate limit. No commit or release may make OIDC routes reachable without D1 verification and these D4 protections; CI must assert the route/method policy, including valid cross-site callback, invalid browser-write Origin, and replay cases. The PKCE verifier must not be recoverable from a stolen cookie alone; no open redirect is allowed; cookie path must work on the public SPA origin. Update async callers if session lookup/revocation becomes async. Perform the full OpenAPI/route-policy/allowlist chain for changed backend routes. |
| **T25 — Customer identity expansion gate** | D5 | Do not implement SAML, SCIM, MFA passthrough, or entitlements until a concrete customer requirement and owner exist. Record the required capability, fail-closed contract, and UI/API/worker coverage before scheduling implementation. |

### Wave 4 — Provider and deployment work

| Packet | Register scope | Work and exit condition |
|---|---|---|
| **T26 — Control-plane runtime contract** | A4 | Select the stateless/read-only runtime model: lifecycle metadata remains in operator state; the API must not present an empty in-memory registry as durable truth. Assert the chosen behavior and align process-contract checks and documentation. Do not add a persistence service. |
| **T27 — Rollback evidence path** | E3 | First verify the existing generic `rollback-execution-verification.yml` workflow attaches `.execution` and invokes the strict verifier with `--record`; inspect `tests/test_rollback_workflow_wiring.py` and identify a concrete remaining gap, if any. Implement and test only that gap, including a Darkube-specific path only if evidence shows it is required. Do not duplicate an existing route. The live paired rollback rehearsal remains a separate provider-gated result. |
| **T28 — Provider backup/restore gate** | E1 | Wait for provider selection and its API contract. Until then, do not invent provider calls or evidence; keep local/test-only behavior explicit. Once triggered, implement and rehearse against provider-issued backup/restore IDs. |
| **T29 — Runtime adapter gate** | E2 | Wait for a real deploy target and runtime contract. Any adapter implementation must be exercised against that target; otherwise document the local adapter's limits and keep the item blocked. |
| **T30 — Kubernetes target gate** | E4 | Build SPA/BFF manifests only after a deployment target, image digest contract, secret source, ingress, and namespace are selected. Replace all placeholders and validate rendered manifests in CI; do not treat placeholders as deployable infrastructure. |
| **T31 — Human operational and deployed-edge gates** | E5, E6, P0-4 deployed remainder | Track a named operations owner, explicit real-data approval, and deferred Phase 3 scope as owner-supplied gates. After a real target and ingress are selected, prove that a caller-supplied `X-OKR-Client-IP` is overwritten at the edge and the BFF is reachable only through that edge; retain overwrite and direct-BFF reachability evidence. An actual nginx configuration harness may establish overwrite behavior, but local SPA relay tests or manifests cannot close deployed reachability. No agent may fabricate or infer target or owner facts. |

### Wave 5 — Independent P0 evidence and disposition

Packet IDs T32–T35 append to the original numbering; their execution dependencies below override numeric order. T33 must precede T24, while T32 follows T02/T03 and T35 follows T32.

| Packet | Register scope | Work and exit condition |
|---|---|---|
| **T32 — PostgreSQL snapshot read-path budget** | P0-3 | After T02/T03, use existing `OKR_TEST_POSTGRES_URL` and the CI PostgreSQL service in `.github/workflows/ci.yml` to extend `tests/test_read_path_budget_postgres.py`. Drive an actual `ritual.snapshot` HTTP request with `pg_read_path` real data through `backend_app/read_query_helpers.py:386-520`; use `measure()`/counters for scope resolutions, statements, checkouts, and new physical connections, including TCP fan-out. Exercise the HTTPS SQLSTATE-42883 RPC-missing fallback alongside `tests/test_ritual_snapshot_rpc.py`. No mock database or scope resolver may stand in for budget acceptance. CI must fail if the PostgreSQL fixture is absent; a local skip, SQLite HTTP 500, or static estimate is not acceptance. Record measured values and behavior. |
| **T33 — SPA-to-BFF private client-IP boundary** | P0-4 repository remainder | Before T24's IP-keyed limiter, add behavioral cases in `spa-web/src/lib/bff-proxy.test.ts` for `spa-web/src/lib/bff-proxy.ts:91-103`: an edge-provided `X-OKR-Client-IP` passes to the BFF, an absent private header stays absent, and `X-Forwarded-For` and `X-Real-IP` are excluded even when present. The SPA relay cannot distinguish an edge-provided private header from a caller-supplied one; do not claim spoof rejection from this test. Preserve `docs/client-ip-trust-adr.md` and existing later-boundary tests (`spa-bff/test/forwarded_ip.test.ts`, `tests/test_rate_limit_key_trust.py`, `tests/test_login_throttle_key.py`). T31 owns edge overwrite and direct-BFF reachability proof. |
| **T34 — Callerless identity-control disposition** | P0-5 | After T22/T23/T25 (and coordinate T19), inspect only `revokeSessionsForIdentity` in `spa-bff/src/session.ts` and `src/saas/identity_ports.py`. If the approved identity design needs either, prove a real production caller and request/lifecycle behavior, including a negative case, in `spa-bff/test/identity_session_revocation.test.ts` or `tests/test_saas_identity_ports.py` as appropriate. Otherwise remove or relabel the inert control and claims. Green isolated unit tests do not prove production reachability. Do not reopen P0-6/D3a or expand customer features without T25's trigger. |
| **T35 — PgBouncer transaction-pooling verification** | P0-8 | After T32, add `tests/support/pgbouncer/pgbouncer.ini` in transaction mode and wire a real PgBouncer service/config artifact in CI between the read-path harness and PostgreSQL. Use `OKR_TEST_PGBOUNCER_URL`; run the same `pg_read_path` real HTTP request via actual `src.database._create_engine` with `OKR_DB_USE_NULL_POOL=true` and `false` (`src/database.py:147-184`). CI must fail rather than skip if the pooler is absent. Retain topology-backed before/after behavior, statements, checkouts, and new physical connections, plus server-side-cursor/session-state tripwires. Direct PostgreSQL or mocked engines are insufficient. Keep default true (`docs/CONFIG_REFERENCE.md:54-55`) if topology/evidence is unavailable; consider a flip only after the evidence passes. |

### Phase 1 P0-to-packet map

| Register row | Packet and remaining acceptance |
|---|---|
| P0-1 | T00/T01 closed baseline history; its SQLite and PostgreSQL measurements are distinct, and T32 must independently measure the snapshot kind. |
| P0-2 | T02 predicate decision, owner/assignee row parity, and explicit task-error behavior. |
| P0-3 | T32 non-skipping PostgreSQL `ritual.snapshot` budget and HTTPS fallback. |
| P0-4 | T33 SPA-web→BFF edge-provided header, absence and forwarding-header exclusion; T31 caller-spoof overwrite and real target/ingress reachability. Repository completion does not close deployed verification. |
| P0-5 | T34 disposition of only the two callerless controls, after T22/T23/T25 and coordinated with T19. |
| P0-6 | T00/T01 closed baseline history; throttle-key closure depends on the P0-4 trusted-IP boundary, not proof of deployed P0-4. |
| P0-7 | T00/T01 closed baseline history; removal of misleading dependency monkeypatches does not claim broader auth-matrix coverage. |
| P0-8 | T35 real PgBouncer transaction-pooling verification before any default change. |

### Hard dependencies and ordered integration

| Prerequisite | Dependent work / required order |
|---|---|
| T00 and T01 | Reconcile all 55 A–F/P0 rows, packet map, self-scan, and conflicts before downstream implementation. |
| T03 with T02 | Serialize the same read paths; decide P0-2 visibility before either predicate changes. T32 follows both. |
| T06 | Fresh full clone and clean verification before subsequent npm lockfile edits, including T18's JOSE dependency. Block while the required clone is unavailable. |
| T11/T12/T15 and T05 | T13 measures final cache/navigation behavior and reconciles backlog probe wording after T05. T16 shares their frontend files and must integrate serially. |
| T17, T18, T19, T20, T21, T22→T23, T33 | T24's D2+D4 unit integrates only after single-authority, verified-token, provisioned-link, verified-email, revocation, approved D3 design where applicable, and trusted-IP boundary contracts are resolved. T18 is a non-negotiable exposure prerequisite. Preserve browser Origin through the SPA proxy for protected methods; allow only the validated cross-site callback exception. External IdP and target facts remain gates. |
| T19 target recount | Before production identity integration implementation; migration/backfill remain blocked without current target invariant and authorized provisioning path. |
| T22 owner decision and T23 implementation, with T25 customer gate | T34 follows and resolves only the two P0-5 callerless controls. Customer feature expansion needs T25's concrete trigger. |
| T32 PostgreSQL budget | T35 uses its harness, then measures NullPool/default and QueuePool opt-in through PgBouncer before any default change. |
| Real provider/target/ingress/owners | T28–T31 and live E3 rehearsal remain externally gated; T31 cannot close P0-4 from local evidence. |

### Shared-file and interface conflict matrix

One integration steward owns each shared file at a time. Reserve exact files and tests in packet briefs; integrate overlapping edits serially, even when packet implementation can proceed independently.

| Packet pair or lane | Shared file/interface | Integration control |
|---|---|---|
| T00↔T01; all document packets↔canonical register/status steward | `docs/REMAINING_ENGINEERING_PLAN.md`, quality baseline and evidence/status claims | Independent T01 audit; one canonical register writer, with aggregate QG counts after integration. |
| T02↔T03↔T32 | `backend_app/read_query_helpers.py`, `backend_app/response_scope_helpers.py`, read actor contract, parity and budget tests | Decide visibility first, serialize read-path changes, then measure final PostgreSQL path. |
| T07/T13/T24/T27/T30; T32/T35 CI topology | `.github/workflows/ci.yml`, release workflows and workflow tests | One workflow integration lane; preserve distinct PR fixture and release/provider gates. T04 reads these contracts for verification and does not reserve an edit lane absent a proven regression and scoped plan update. |
| T05↔T13 | `docs/architecture/ARCHITECTURE_BACKLOG.md` performance-probe claim | Reconcile wording against implemented budget evidence. |
| T06↔T18 and all later npm edits; T16 image metadata | npm lockfiles, BFF package manifest, digest-pinned image and Node engine declaration | T06 fresh-clone repair first; serialize later dependency edits; inspect exact runtime before engine changes. |
| T11↔T12↔T14↔T15↔T16; T13↔T11/T12/T15 | `spa-web` shell/routes/hooks, `resourceCache.ts`, panel components, route E2E data | Reserve warning and UI files; measure final cache, navigation and request waterfall. |
| T17↔T21↔T23; T23↔T18/T19/T20/T24 | BFF session/claims and async callers, backend identity response, generated session schema | T22 decision gates T23; integrate identity shape and route effects before T24 release. |
| T19↔T23↔T26 | `backend_app/main.py`, routers/schemas, exported OpenAPI, generated clients, route policy, allowlist, auth matrix | T26 checks whether its runtime choice changes a route/schema; one steward runs the full contract chain for each integrated route set. |
| T08↔T02/T03/T19/T21/T23/T26/T32 | `backend_app` typing debt versus read/security/router work | Assign exact T08 files before dispatch; serialize collisions and recount. |
| T09↔T02/T03/T17/T19/T23/T35 | `src` typing debt versus service/model/database work | Assign exact T09 files before dispatch; serialize collisions and recount. |
| T10↔all test/script authors, including T02/T03/T07/T13/T18–T24/T26/T27/T32/T34/T35 | `tests` and `scripts` mypy debt versus focused behavioral tests and checkers | Assign exact T10 files; one owner edits any shared test/script at a time. T04 verifies existing tests without authoring new ones unless a scoped plan update follows a proven regression. |
| T32↔T02/T03/T35 | PostgreSQL budget harness, `ritual.snapshot` read dispatch, CI service topology | Measure after parity/actor changes; T35 reuses the final harness with a real pooler. |
| T33↔T24/T31 and frontend BFF proxy tests | `spa-web/src/lib/bff-proxy.ts`, its test, trusted-IP and Origin relay contracts, deployed edge | Test SPA hop before IP-keyed limiter; coordinate T24 Origin relay; retain T31 spoof-overwrite and direct-BFF deployed proof. |
| T34↔T22/T23/T25, coordinated with T19 | `spa-bff/src/session.ts`, `src/saas/identity_ports.py`, identity callers and acceptance claims | Decide architecture and customer trigger first; prove production reachability or remove/relabel only the inert controls. |
| T35↔T32/T13/CI topology | PostgreSQL budget counters, `src/database.py`, CI service topology and performance claims | Pooler evidence follows T32; keep backend pooling separate from browser budget, and serialize CI edits. |

### Packet self-consistency preflight

Check these 36 rows against the current register before dispatch. Each row states the acceptance boundary; a row is not proof that its packet has passed.

| Packet | Scope and self-consistency condition |
|---|---|
| T00 | All 55 A–F/P0 rows; distinguish repository evidence from external facts and closed P0 history. |
| T01 | Independent audit of status, 36 IDs, P0 map, conflict ownership and D1/D2+D4 gates. |
| T02 | F1/P0-2: choose task visibility before code; test owner and assignee rows and injected errors. |
| T03 | F2: all seven enumerated read kinds reject actorless access. |
| T04 | A3 Done: verify existing promotion `phase-1-evidence` dependency and PR fixture suite; F6 awaits real provider evidence. Report any regression before a scoped code plan. |
| T05 | B2/B4: preserve ADR-001/history and align probe claim with T13. |
| T06 | F5: current advisory and genuine fresh/clean clone evidence; no hand-edited lockfile. |
| T07 | F8: inventory, positive/negative fixtures and real workflow execution. |
| T08 | QG-002 backend files assigned exactly; count after shared edits. |
| T09 | QG-002 runtime-core files assigned exactly; count after shared edits. |
| T10 | QG-002 tests/scripts assigned exactly; integrate milestone counts after test authors. |
| T11 | C1/C8 cache and shell behavior; no session cache, warmed drill remains required. |
| T12 | C2 route split; access checks prevent authenticated chrome flash. |
| T13 | C3 browser waterfall/warmed probe only; final frontend behavior and pinned conditions. |
| T14 | C5 signed-in password change, with success/failure paths. |
| T15 | C6 actual role-specific route visits and isolated data. |
| T16 | C4 exact image/CI Node observation precedes engine edit; frontend warnings owned. |
| T17 | D6 single BFF session authority; external-consumer search gates Python deletion. |
| T18 | D1 audited JOSE verification before any OIDC exposure. |
| T19 | D8 target recount before integration; migration/backfill and provisioned-link authorization gate. |
| T20 | D9 boolean `email_verified` true and owner-confirmed IdP guarantee. |
| T21 | D7/D10 next-proxied-request revocation across full protected matrix; account-wide semantics explicit. |
| T22 | D3 owner decision; unknown-ID/per-session acceptance cannot change silently. |
| T23 | Approved D3 design and legacy cutover; cross-instance/store-outage drill as applicable. |
| T24 | D2+D4 indivisible after D1/T33; exact Origin on browser writes, validated cross-site callback exception, and rate-limit key from private `X-OKR-Client-IP` or raw peer only. |
| T25 | D5 customer requirement and owner gate before feature scheduling. |
| T26 | A4 stateless/read-only runtime contract; reserve API artifacts if routes change. |
| T27 | E3 inspect existing strict `--record` path first; live paired rehearsal stays external. |
| T28 | E1 provider API/issued IDs before backup/restore claim. |
| T29 | E2 real target/contract before runtime adapter claim. |
| T30 | E4 target, ingress, secrets, image and namespace before manifest claim. |
| T31 | E5/E6 and P0-4 deployed edge; prove spoofed private-header overwrite and no direct-BFF reachability. |
| T32 | P0-3 non-skipping `OKR_TEST_POSTGRES_URL` real HTTP snapshot budget and SQLSTATE-42883 fallback. |
| T33 | P0-4 SPA→BFF edge-provided header pass/absence and XFF/X-Real-IP exclusion; T31 owns spoof overwrite. |
| T34 | P0-5 exact two callerless controls after identity decision; real caller or inert-control disposition. |
| T35 | P0-8 `OKR_TEST_PGBOUNCER_URL` real transaction pooler, `_create_engine` branches and non-skipping CI. |

## Decision and Integration Rules

- **D3 remains an explicit owner decision.** T21 establishes the next-request `token_version` behavior; T22 then compares it with D3's per-session requirements. The register's lighter alternative may be chosen only if the owner accepts account-wide invalidation and formally revises any incompatible D3 acceptance criteria. Otherwise, use the shared per-session service. This prevents agents from building a larger service by default or silently weakening the requirement.
- **OIDC exposure is atomic.** T18 is a hard prerequisite. T24 combines D2 and D4 in one integration/review/release unit. CI must assert rate-limit coverage using the private `X-OKR-Client-IP` or, when absent, the raw immediate peer; `request.ip` under `trustProxy`, `X-Forwarded-For`, and `X-Real-IP` are not trusted client keys. CI must also assert the route/method-specific Origin policy: exact public SPA Origin on browser-initiated POST login and POST authorize initiation, logout, and authenticated mutations; preserve that Origin through the SPA proxy. The cross-site top-level GET callback is exempt from Origin comparison only at the fixed redirect URI and with valid browser-bound `HttpOnly`/`SameSite=Lax` transaction cookie, single-use state, nonce and PKCE. Test valid cross-site callback, invalid Origin on browser writes, and replay. No independent D2 or D4 release.
- **Shared API artifacts are integration-owned.** Backend route authors supply code and tests; the integration steward performs the ordered OpenAPI/client/route-policy/allowlist regeneration and commits the resulting set together. Generated-file drift and mutation-auth-matrix checks must pass before merge.
- **Dependency lockfiles are serialized.** T06 is a genuine fresh clone and is completed before any other npm dependency update. The audited JOSE dependency, if used, is integrated afterward by the same lockfile steward; it must not race T06.
- **F8's checks must demonstrably execute.** A passing source-string assertion is not evidence. Each script gate has a deliberately bad fixture that fails and a good fixture that passes, and the CI/job wiring test proves the invocation occurs using `python -m scripts.X` where applicable.
- **Baseline audit is independently reviewed.** T01 checks all 55 register rows and progress tables line-by-line, verifies the 36 unique contiguous T00–T35 IDs, P0 and A–F mapping, every self-consistency row, shared-file conflicts, and D1/D2+D4 ordering before downstream work is assigned.

## Acceptance and Release Gates

- Per-packet focused tests and acceptance criteria remain those in the canonical register; add behavioral tests for each discovered failure mode rather than source-text checks. P0-2 requires the visibility decision plus owner/assignee parity and non-silent error behavior. P0-5 requires a production caller with a negative case or a documented removal/relabel of both inert controls.
- P0-3 requires a non-skipping `OKR_TEST_POSTGRES_URL` PostgreSQL `ritual.snapshot` real HTTP budget with scope, statement, checkout, new physical-connection and SQLSTATE-42883 HTTPS RPC-fallback evidence. P0-8 requires non-skipping `OKR_TEST_PGBOUNCER_URL` real transaction-pooler before/after evidence from both `_create_engine` pool branches; keep the default true until that exists. P0-4 needs both T33's SPA→BFF forwarding/absence tests and T31's caller-spoof overwrite and deployed edge-only reachability result before its register row can be verified.
- Final repository checks: `just check`, `python scripts/check_docs_hq_links.py`, and `python scripts/check_quality_gate_baseline.py` when their launchers are available. Run the register's warmed-stack frontend drill and the D3 cross-instance drill for their respective packets. A denied launcher is recorded as unavailable, not counted as a pass.
- OIDC integration tests use a mock IdP for a valid cross-site callback/code flow plus invalid browser-write Origin, replayed state, nonce mismatch, tampered code, unsigned/forged token, unsupported algorithm, wrong issuer/audience, expired token, and missing/false/non-boolean `email_verified`. The release workflow must remain unable to expose OIDC until the D1/D4/D2 coupled check passes.
- Promotion evidence checks remain blocked until provider-issued records, measured RPO/RTO, attestation, named owner, and real-data approval exist. Fixture tests in CI do not count as provider evidence. T27's current strict `--record` workflow must be assessed before code changes; live paired rollback remains provider-gated.
- Close a packet only with the required integrated change, green required CI, its stated runtime/behavior drill, and an updated authoritative A–F or P0 register row with evidence. When this managed checkout cannot create commits, record file snapshots and review evidence; do not claim merge or remote CI. Keep external/deferred packets explicitly blocked with trigger conditions.

## Fixed Assumptions

- The current register state is re-derived at T00 across 55 A–F/P0 rows; no claim in this file overrides it. In particular, D2 is not started unless current evidence changes that status. P0-1/P0-6/P0-7 remain qualified closed history, P0-2/P0-3/P0-5/P0-8 remain open, and P0-4 awaits deployed verification.
- D4 uses the selected route/method policy: exact configured public SPA Origin on browser-initiated POST login and POST authorize initiation, logout, and authenticated writes, with that Origin preserved through the SPA proxy. The cross-site top-level GET OIDC callback is exempt from Origin comparison only under the fixed redirect URI and browser-bound transaction checks stated above. CSRF protection applies to logout and authenticated state-changing routes, with no pre-login CSRF bootstrap. Rate limiting is IP-keyed and in-process, with per-replica scaling documented. The callback exception follows the canonical cross-site redirect contract; its cost is the absence of an independent Origin-header check, bounded by the transaction and redirect validation.
- D7's selected latency is the next proxied request. It does not decide whether account-wide versioning alone satisfies D3's separate per-session acceptance.
- The control-plane choice is stateless/read-only. Provider and IdP facts remain human gates; code may be prepared against fixtures but production enablement waits for real configuration.
- Node engine metadata changes only after the exact Node version in the digest-pinned image and CI runtime is observed and compared.
