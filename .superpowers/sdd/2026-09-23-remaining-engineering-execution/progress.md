Documentation HQ: [README](../../../README.md)

# Remaining Engineering Execution — SDD Progress Ledger

Plan: `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md`
Canonical status register: `docs/REMAINING_ENGINEERING_PLAN.md`
Workspace: `.superpowers/sdd/2026-09-23-remaining-engineering-execution/`
Execution constraint: `.git` is read-only in this managed workspace (`index.lock` creation denied); task commits, branches, and git worktrees are unavailable. Work in the current writable checkout under the Superpowers fallback; disjoint file-reserved packets may run in parallel, while every shared file/contract lane is serialized. Keep per-task reports, snapshots, tests, and independent reviews. No user files were discarded.

## Preflight conflict matrix

| Task pair / lane | Shared state or dependency | Control |
|---|---|---|
| T00 ↔ T01; all doc packets ↔ canonical register steward | all 55 A–F/P0 rows, `docs/REMAINING_ENGINEERING_PLAN.md`, quality/status claims | T01 independently audits T00; one register writer and cross-signoff before code packets |
| T02 ↔ T03 ↔ T32 | backend read paths, actor contract, PostgreSQL budget | visibility decision before predicate edits; serialize, then measure real HTTP snapshot path |
| T07/T13/T24/T27/T30; T32/T35 CI topology | `.github/workflows/ci.yml`, release workflows and wiring tests | T13 coordinator is the single workflow steward until T13 integration/review completes. T07/T27 complete; T24/T30 externally blocked; T32/T35 lack real DSNs. No overlapping workflow edits. T04 reads existing A3 contracts and reserves no edit absent proved regression/scoped plan update. |
| T05 ↔ T13 | roadmap/backlog probe claim and performance definition | reconcile wording after actual T13 budget evidence; validate Docs HQ links |
| T06 ↔ T18 and later npm edits; T16 | lockfiles, JOSE dependency, Node image/engine metadata | fresh full clone for T06; serialize lockfiles; observe exact runtime before engines edit |
| T11/T12/T14/T15/T16; T13 ↔ T11/T12/T15 | SPA shell/routes/hooks, lint findings, cache/waterfall and E2E data | reserve exact frontend files; integrate serially before final budget |
| T17 ↔ T21 ↔ T23; T23 ↔ T18/T19/T20/T24 | BFF session/claims, backend identity response, generated schema, async callers | T22 owner decision gates T23; T24 D2+D4 is indivisible. A T15-discovered non-auth 429 misclassification is isolated to a T17 follow-up; no D3/D4 route work. |
| T19 ↔ T23 ↔ T26 | backend routers/schemas, OpenAPI, generated clients, allowlist/auth matrix | T19 target recount before production integration; one steward runs full route-contract chain. T26 steward owns lifecycle POST removal and its OpenAPI/generated-artifact chain; do not touch shared T19/T23 declarations. T02 is complete, so T26 may narrowly reconcile the obsolete assertions in the shared control-plane route test while preserving unrelated T02 edits. |
| T08 ↔ T02/T03/T19/T21/T23/T26/T32 | `backend_app/main.py`, `backend_app/observability_http.py`; read helper reserved | owns only the 12 errors in two files; excludes `read_query_helpers.py` for T02/T32 and response/read routes outside its slice |
| T09 ↔ T02/T03/T17/T19/T23/T35 | `src/crud_auth_helpers.py`, `src/saas/{backup_operations,environment_contract,file_lock,operator_credentials,provisioning,release_operations}.py`, `src/services/app_shell_runtime.py`, `src/utils/sync.py` | owns only 39 errors in nine files; excludes `src/services/supabase_api_mode_read.py` for T02 |
| T10 ↔ all test/script authors | two CLI scripts and 16 exact tests in `task-T10-brief.md` | owns 106 current errors in 18 files; excludes T02 read-parity targets and T03/T07 files without current errors; one owner per file |
| T32 ↔ T02/T03/T35 | `tests/test_read_path_budget_postgres.py`, CI PostgreSQL/Pooler topology | use real `pg_read_path`/`measure()` after parity; T35 follows T32 |
| T33 ↔ T24/T31 and frontend BFF proxy tests | `spa-web/src/lib/bff-proxy.ts` and test, private IP and Origin relay, deployed edge | T33 tests pass/absence/XFF/X-Real-IP exclusion; T31 proves private-header overwrite/direct-BFF reachability |
| T34 ↔ T22/T23/T25, coordinated with T19 | `spa-bff/src/session.ts`, `src/saas/identity_ports.py`, caller evidence | approved design/customer trigger before production caller or inert-control disposition |
| T35 ↔ T32/T13/CI topology | PostgreSQL counters, `src/database.py`, PgBouncer service/config, browser budget claims | real transaction pooler and both `_create_engine` branches; backend pooling distinct from T13 |
| T28 ↔ T29 ↔ T30 ↔ T31 | external provider/target/owner facts | remain blocked until supplied; do not fabricate |

## Packet checklist

- [x] T00 Register reconciliation (local report and canonical corrections reviewed; no Git/CI closure)
- [x] T01 Independent baseline audit and final cross-signoff (local; external gates remain)
- [x] T02 Read-path payload parity (69 focused tests; scoped mypy/Ruff/format pass; independent review PASS. Assignee-only context contains only parent IDs/titles per user decision; two unrelated read-helper mypy diagnostics remain.)
- [x] T03 Actor-presence audit (seven kinds, behavioral negative/positive controls, independent review PASS; no production edits)
- [x] T04 Evidence gate verification and disposition (A3 has no local wiring gap; F6 remains external)
- [x] T05 Roadmap and backlog truth (two owned documents; one review fix round; scoped re-review PASS)
- [x] T06 Fastify advisory and lockfile repair
- [x] T07 Script enforcement inventory (25 dispositions, two required repo-local CI gates; independent review PASS)
- [x] T08 Mypy burn-down: backend app (complete locally; independent review PASS; assigned-file errors 12→0; 131 focused tests and Ruff pass; full-repository mypy remains failing on unrelated debt)
- [x] T09 Mypy burn-down: runtime core (39 original assigned diagnostics resolved; protocol split and falsey-provider validation regression independently reviewed; focused suites pass)
- [x] T10 Mypy burn-down: tests and scripts (full-scope follow-up independently reviewed; all 13 T10-owned contextual diagnostics resolved; three reserved T02/T32 read-path errors remain)
- [ ] T11 Cache and shared-shell verification (local inspection and focused tests pass: 85; open PR/commit refresh and warmed-stack drill unavailable)
- [x] T12 Route streaming and code-splitting (independent review PASS after manager sub-tab access leak fix; 39 focused tests, typecheck, build pass; 10 lazy chunks verified)
- [ ] T13 Performance budget (PR waterfall/release measurement implementation underway; #177 refreshed merged; owner-approved numeric frontend budget absent, so probe will report unscored and C3 stays open)
- [ ] T14 In-app password change
- [x] T15 Frontend route E2E (full opted-in module 6/6 twice, including independent reviewer rerun; Ruff/py_compile and 25 support-read tests pass; independent review PASS)
- [ ] T16 Runtime version and lint findings (partial; independent review PASS; exact hosted Node patch and deferred F3 warning decisions remain open)
- [x] T17 Single session authority
- [x] T18 ID-token verifier (isolated implementation; exact `jose` 6.2.12; 16 verifier + 117 BFF tests, typecheck/build/lint pass; independent security review PASS. T24 owns production issuer and route integration.)
- [ ] T19 Provisioned identity resolution
- [ ] T20 Verified-email contract
- [ ] T21 Token-version enforcement
- [ ] T22 D3 architecture decision
- [ ] T23 Implement approved D3 design
- [ ] T24 Coupled D4 + D2 integration unit
- [ ] T25 Customer identity expansion gate
- [x] T26 Control-plane runtime contract (57 focused runtime/process/API tests; 51 contract tests; OpenAPI/schema/operation outputs regenerated; independent review PASS)
- [x] T27 Rollback evidence path (55 focused tests; timezone-aware and missing-field cases; workflow wiring pinned; independent review PASS. Live paired rehearsal remains provider-gated.)
- [ ] T28 Provider backup/restore gate
- [ ] T29 Runtime adapter gate
- [ ] T30 Kubernetes target gate
- [ ] T31 Human operational and deployed-edge gates
- [ ] T32 PostgreSQL snapshot read-path budget
- [x] T33 SPA-to-BFF private client-IP boundary
- [ ] T34 Callerless identity-control disposition
- [ ] T35 PgBouncer transaction-pooling verification

## Findings carried from adversarial review

- Register is authoritative: D1/D2/D5/D7 not started; D3a closes same-process replay only.
- Exact packet set is T00–T35 (36 unique contiguous tasks); never conflate packet Txx with register Dx/P0-x.
- D2 and D4 remain atomic and cannot expose OIDC routes before D1 and protections pass.
- T22 owns the D3 options decision; token_version does not claim unknown-SID or per-session semantics absent owner revision.
- T06 requires genuine fresh clone; do not hand-edit npm lockfiles.
- F8 validators require positive/negative fixtures and workflow execution evidence.
- Do not modify Node engine declaration until digest-pinned image and CI Node versions are measured.

## Task reports

Task reports, briefs, snapshots, and review notes are stored in this directory. Baseline checks and T00/T01 cross-signoff passed; packets now proceed only after their individual dependency, owner, exact-file-reservation, and evidence gates are satisfied.

## Baseline (2026-09-23)

- `npm run typecheck`: PASS (web and BFF).
- `npm run lint`: exit 0, 8 existing unused-variable warnings (AtlasShell, InspectorAlignmentPanel, useAdminActions, useInspectorAuxData).
- `.venv\Scripts\ruff.exe check backend_app scripts tests`: exit 1, one existing F841 (`tests/test_dual_mode_parity.py:637`, unused `scope`).
- `.venv\Scripts\pytest.exe -q`: 1321 passed, 12 skipped, 2 warnings, 164.48s. Warnings: Starlette/httpx deprecation and pytest cache write denied.
- Current QG-002 remeasurement: `.venv\Scripts\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip backend_app src scripts tests` found **160 errors in 31 files** (backend_app 14/3 files, src 40/10, tests/scripts 106/18). The register's 127-error figure is explicitly dated 2026-09-20. Exact per-packet file reservations are in T08–T10 briefs.
- `uv run` could not initialize the user-level uv cache; `.venv` binaries were used directly. `just` and Bash helper execution denied by managed environment.
- `.git` is read-only; commit/worktree creation denied. All packet work is serial in this checkout with pre/post snapshots and reviewer reports. Git status includes pre-existing authored plan+README changes; no files were cleaned.

Ruling: use the current writable checkout with exact file reservations, parallelizing only disjoint packets and serializing shared lanes because managed permissions deny all `.git` writes — this preserves usable agent concurrency without risking colliding edits — cost if wrong: without worktree-level isolation, a missed overlap can mix task changes and require file-snapshot recovery.
Ruling: follow Superpowers' per-task implement-review sequence even though the request says an army — the required task gates and shared files make concurrency unsafe here — cost if wrong: slower delivery and fewer simultaneous agents.

Task 0 (T00): complete locally — register reconciliation and all canonical corrections are independently reviewed; the packet has no commit/CI closure because `.git` is read-only.

- T00 implementer returned: 47 register entries reconciled; only stale Workstream F preface changed; exact doc-link and quality baseline checks passed. Review pending. Git diff range replaced by scoped file diff due read-only .git.

- T00 fix round 1: implementer amended D5 status and D8/E2 paths/search scopes; re-ran doc-link and quality baseline checks successfully. Scoped re-review pending.

Task 0 (T00): historical one-round completion note superseded. T00 required later P0/status/B5 and canonical D2/D4 corrections; final T00/T01 cross-signoff remains pending independent review.

## Packet self-consistency scan (pre-dispatch)

| Packet | Self-consistency check | Result / gate |
|---|---|---|
| T00 | Reconcile all 55 A–F/P0 rows, avoid inferring external facts | report and canonical correction review PASS; final T00/T01 cross-signoff PASS locally |
| T01 | Independently audit register, 36 packets, P0 map and conflicts | final cross-signoff PASS; owner and external evidence gates retained |
| T02 | F1/P0-2 predicate decision, owner/assignee parity, task-error behavior | PASS: 69 focused tests; six-kind parity; minimal assignee-only parent IDs/titles; sanitized task-query errors; behavioral check-in exclusions; independent review PASS. Two unrelated mypy diagnostics remain in the shared read helper for T32. |
| T03 | Trace actor presence across seven enumerated kinds | PASS: 36 backend + 23 BFF tests; actorless/mismatched requests rejected before protected reads, authorized controls reach real scope paths; independent review PASS. See `task-T03-report.md` and `task-T03-review.md`. `node.get` Goal/Task serialization still raises a separate DetachedInstanceError after authorization and is not fixed by T03. |
| T04 | A3 Done: refresh existing promotion placement and PR fixture evidence; F6 external | PASS: 71 focused tests; BLOCKED bundle failed closed as expected; independent review PASS; no code gap. See `task-T04-report.md` and `task-T04-review.md`. |
| T05 | Roadmap/backlog claims aligned with current authoritative plan | PASS after one fix round: 91-file Docs HQ and 18 direct links pass; performance points to T13/current register; tenant/RLS rejection unconditional. See `task-T05-report.md`, `task-T05-review.md`, and `task-T05-rereview.md`. |
| T06 | Advisory refresh + lockfile repair + clean clone checks | consistent; genuine full clone mandatory; stop on repeated stale failure |
| T07 | Inventory scripts before wiring/removal | PASS: 25 dispositions = 2 deterministic CI gates + 7 imported helpers + 16 operator commands; 30 focused tests pass, including real positive/damaged command fixtures; independent implementation/register reviews PASS. See `task-T07-report.md`, `task-T07-review.md`, `task-T07-rereview.md`, and F8 register-review reports. New workflow test is visible/untracked until writable Git integration. |
| T08 | Mypy backend_app slice | PASS locally: 12 assigned errors resolved in two exact-owned files; 131 focused tests, Ruff, independent review pass; full-repository QG-002 still has unrelated debt |
| T09 | Mypy src runtime core slice | PASS locally: 39 original assigned diagnostics resolved across nine source files; protocol split reviewed; falsey restore-provider regression fixed and reviewed; focused tests/Ruff pass; T02's reserved `supabase_api_mode_read.py` remains separate |
| T10 | Mypy tests/scripts slice and aggregate milestones | PASS locally after full-scope follow-up review: all 13 T10-owned contextual diagnostics resolved; full repository now has only three T02/T32-reserved read-path errors; see `task-T10-report.md` and full-scope review artifacts |
| T11 | Verify existing cache/shell behavior; no session caching | consistent; C8 remains open until warmed drill |
| T12 | Route suspense/errors with auth/deep-link preservation | PASS locally after review fix: auth/role/admin-tab readiness gates shell chrome; 10 distinct panel chunks, loading/error/not-found boundaries; 39 focused tests, typecheck/build and independent review pass; T15 E2E/T13 workflow files untouched |
| T13 | Frontend PR waterfall and pinned warmed release probe | C3 reconciliation independently reviewed PASS; T15 full suite/review PASS; PR #177 refreshed as merged (`3e35315`). Coordinator owns shared workflow lane. Local deterministic CI and protected measurement-only artifact can be implemented. No numeric authenticated SPA budget is defined; probe must report `unscored` until release-owner approval. C8 warm drill and actual warmed-stack artifact remain separate gates; T32/T35 remain backend budgets. |
| T14 | Signed-in password-change journey | consistent; retain authentication and success/failure tests |
| T15 | Role-parameterized route E2E | PASS locally: admin/manager/member rendered routes; admin users/teams/backup/audit, manager Cycles-only, direct member Admin denial, deep-link reload, alignment and rendered RTL. Full module passed 6/6 twice, including independent reviewer rerun; fixture-only rate-limit ceiling prevents synthetic same-loopback client aggregation. Narrow alignment/work-history support read fixes have regression tests. See final report/review. |
| T16 | Observe exact image/CI Node versions before metadata edits | consistent; leave engines unchanged if evidence missing |
| T17 | Establish single BFF session authority | D6-1 complete. Separate T15-discovered follow-up distinguishes explicit 401/403 auth rejection from 429/5xx: reject clears cookie; transient status preserves cookie/fails closed. Full BFF suite 120 passed; typecheck/build/scoped ESLint pass; independent follow-up review PASS. External consumer evidence still gates deleting Python pair. |
| T18 | Verify ID tokens before trusting claims | PASS isolated verifier: RS256/ES256/PS256, bounded JWKS, bounded ASCII `sub`, issuer/audience/`azp`, exp/iat/nonce; 16 focused + 117 BFF tests and typecheck/build/lint pass; independent security review PASS. No route integration; T24 owns approved issuer configuration. |
| T19 | Resolve preprovisioned issuer/subject links | target recount before production integration; migration/backfill authorization gate |
| T20 | Require boolean true email_verified; owner confirms IdP guarantee | consistent; production login blocked absent evidence |
| T21 | Enforce token_version on every protected route | consistent; test full route matrix/account-wide semantics |
| T22 | Decide D3 account-wide vs durable per-session behavior | consistent; owner decision precedes implementation |
| T23 | Conditional implementation after T22 | consistent; no work before approval; unknown IDs fail closed if per-session chosen |
| T24 | D2+D4 indivisible; route/method Origin, callback exception and trusted limiter key | D1 prerequisite; preserve Origin through SPA proxy; use private `X-OKR-Client-IP` or raw immediate peer only, never proxy-derived `request.ip`/XFF/X-Real-IP; test valid cross-site callback, invalid browser-write Origin, replay, and limiter-key cases |
| T25 | Gate expansion on concrete customer requirement/owner | consistent; no speculative scope |
| T26 | Stateless/read-only control-plane runtime contract | PASS locally: remove ephemeral lifecycle mutation POST; preserve operator-only inventory GETs as non-authoritative/ephemeral, SQL rollout GET, and operator CLI file-backed operations. Actual-app runtime probe ignores seeded `OKR_CONTROL_PLANE_STATE_PATH`; 57 focused runtime/process/API tests, 51 contract tests, generated contract checks pass; independent review PASS. No persistence service added. |
| T27 | Existing strict `--record` path first; distinct provider rehearsal | PASS locally: malformed, timezone-less, and missing `execution.observed_at` rejected; valid UTC `Z` accepted; workflow wiring pinned; 55 focused tests; independent review PASS. Live paired rehearsal remains provider-gated. |
| T28 | Provider backup/restore waits for provider API/IDs | consistent; no invented calls/evidence |
| T29 | Runtime adapter waits for deploy target/contract | consistent; local limitations remain explicit |
| T30 | Kubernetes manifests wait for deployment inputs | consistent; no placeholder deployability claim |
| T31 | Human gates and P0-4 deployed edge proof | caller-spoofed private-header overwrite and direct-BFF reachability need real ingress/target or actual nginx harness for overwrite |
| T32 | P0-3 PostgreSQL `ritual.snapshot` budget | `OKR_TEST_POSTGRES_URL`, real `pg_read_path` HTTP, `measure()` counters and SQLSTATE-42883 fallback; CI cannot skip |
| T33 | P0-4 SPA→BFF private-IP relay | edge-provided pass, absent case, XFF/X-Real-IP exclusion; no spoof-overwrite claim |
| T34 | P0-5 two callerless identity controls | after T22/T23/T25; real production caller/negative path or remove/relabel inert claims |
| T35 | P0-8 transaction-pooler verification | `OKR_TEST_PGBOUNCER_URL`, real PgBouncer service/config, both `_create_engine` branches and non-skipping CI |

The pairwise conflict matrix above maps shared files/contracts. T01 verified the current packet scope and cross-signed the baseline; exact file reservations remain required before each dispatch.

- T00 round 2 fix report received: 55 A–F/P0 entries; canonical status routing and B5 evidence updated. Documentation link and quality baseline checks passed. Independent review pending.

Ruling: expand the plan from 32 to 36 packets (add T32–T35) — P0-3 PostgreSQL snapshot measurement, P0-4 SPA→BFF behavior, P0-5 callerless identity-control disposition, and P0-8 PgBouncer verification have distinct failure modes and independent acceptance evidence; a dedicated packet for each is easier to review and less coupled than overloading existing frontend/auth tasks — cost if wrong: more coordination and packet bookkeeping than strictly necessary. Preserve T00–T31 numbering and append four packets.

Task 0 (T00): prior local acceptance after two fix rounds was superseded by the canonical D2/D3 assumptions and D4 limiter-key contradictions found in final cross-signoff. The corrections passed two scoped independent reviews; see `task-T00-canonical-fix-review.md` and `task-T00-canonical-fix-review-T00.md`. The local packet is not merged/CI-closed.
Task 0: minor (deferred): T00 report calls E3 code remainder open although the strict `--record` workflow exists; T27 must identify a concrete code gap before changes — risk of overstating work.
Task 0 review outcomes: first review findings D5/D8/E2 addressed; scoped re-review approved. T01's additional P0/status/B5 findings were corrected in round 2 and independently reviewed; no Critical/Important gaps remain.
Task 1 (T01): the original audit and its P0-8 correction are complete; its initial 32-packet finding is historical and superseded by the 36-packet expansion. The final cross-signoff PASS is recorded in `task-T01-cross-signoff.md`. No downstream implementation, merge, remote CI closure, or external drill is claimed. Corrected the P0-8 wording to distinguish PgBouncer text references from missing pooler-backed execution/topology.

- Plan reconciliation implementer returned: 36 unique packets, all T01 corrections and P0-1…P0-8 mapping encoded; docs HQ/quality checks passed. Independent review pending.

Plan-review rulings before fix round 1:
Ruling: T33's SPA unit tests prove forwarding from an edge-provided context and omission of public forwarding alternatives; only an actual nginx/edge harness or T31 deployed proof can establish overwriting of a caller-supplied private header — the SPA relay has no provenance signal — cost if wrong: spoofed private header may be trusted if the edge can be bypassed or misconfigured, so T31 must gate deployed closure.
Ruling: apply exact-Origin comparison to browser-initiated POST login/authorize, logout, and authenticated mutations; exempt the OIDC callback's cross-site top-level GET from Origin comparison only when it matches the fixed callback URI and validates the browser-bound HttpOnly/Lax transaction cookie, single-use state, nonce, and PKCE — the canonical register describes the callback as cross-site and an Origin requirement would reject legitimate IdP returns — cost if wrong: callback origin has no independent header check, mitigated by strict transaction validation and exact redirect binding.

Plan review fix round 1 applied locally: T33 tests edge-provided private-header pass, absence, and exclusion of both `X-Forwarded-For` and `X-Real-IP`; T31 owns caller-spoof overwrite and deployed direct-BFF reachability. T24 specifies SPA-to-BFF `Origin` preservation, exact BFF comparison, the narrow validated cross-site GET callback exception, the ADR-approved private client-IP limiter key and invalid-Origin/replay/key tests while keeping D2+D4 atomic. T32/T35 name real PostgreSQL/PgBouncer DSNs, fixtures, counters, engine branches and non-skipping CI topology. A second scoped plan review and canonical-fix reviews passed; see their reports. No packet is claimed merged or CI-closed.

Ruling: correct the canonical OIDC baseline assumption to the inspected checkout — `spa-bff/src/server.ts` and `spa-web/src/app/api/session/` contain only login/me/logout, D1/D2/D5/D7 are not started, and D3a covers same-process replay only; B7's historical disposition and current work-in-progress remain separate — cost if wrong: implementers may treat nonexistent OIDC routes and incomplete revocation as shipped prerequisites.
Ruling: bind D4 and packet T24's throughput limiter to private `X-OKR-Client-IP`, with raw immediate socket peer fallback only when the header is absent — the settled client-IP trust ADR rejects `request.ip` under unrestricted `trustProxy`, `X-Forwarded-For`, and `X-Real-IP` as client keys; the login lockout retains its distinct no-IP fallback — cost if wrong: a caller can rotate a spoofed forwarding key and bypass rate limits, or an absent-header lockout can become an aggregate denial of service.
Final T00/T01 cross-signoff: PASS locally, after canonical corrections passed scoped independent review. Downstream packets may start subject to individual dependencies, file reservations, owner decisions, and external-evidence gates; no merge, remote CI, or deployment completion is claimed.
Task 4 (T04): complete locally. A3 promotion/fixture contracts verified; 71 focused tests pass, the blocked bundle fails closed as expected, and independent review PASS. F6 remains externally blocked; no provider or promotion evidence is claimed.
Task 5 (T05): complete locally after one scoped review fix. Roadmap and backlog distinguish open repository work from external evidence, preserve ADR-001's rejection of shared-database tenancy/RLS, and point current performance work to the authoritative register/T13. Independent re-review PASS; see task reports. Documentation HQ, 18 direct links, and whitespace checks pass.
Task 3 (T03): complete locally after independent review. All seven kinds refuse absent/mismatched actors on the real backend route; authorized controls reach actor-scoped paths. 36 backend tests and 23 BFF tests pass; no production code changed. Separate follow-up: full `node.get` serialization returns `DetachedInstanceError` for Goal and Task after authorization; preserve this as open read-path defect for T02/coordinator disposition, not T03 closure.
Task 7 (T07): complete locally after one low report-only review correction and canonical F8 reconciliation. Two deterministic repository checks are now required in PR CI; all other candidates have explicit helper/operator dispositions, with no scripts deleted. 30 focused tests pass; the independent code review and two scoped F8 register reviews pass. Hosted CI, branch protection, live provider checks, and operational evidence remain unverified. The new workflow test is present but untracked because `.git` is read-only.

T07 typing follow-up: the new workflow test's PyYAML `import-untyped` diagnostic is cleared with one line-local explained ignore. Real YAML parsing and the positive/damaged workflow assertions remain. Independent review reproduced mypy, pytest (2), and Ruff passes; see `task-T07-mypy-followup-report.md` and `task-T07-typing-followup-review.md`.

Task 8 (T08): complete locally after independent review PASS. The four idempotency wrappers now match `main_runtime_helpers.py` signatures/returns, and observability snapshots data-access context once per metric record. Assigned-file errors fell from 12 to 0; focused tests (131) and Ruff pass. The full repository remains at 135 errors during concurrent T09/T10 work; no global post-packet total is claimed. See `task-T08-report.md` and `task-T08-review.md`.

Task 11 (T11): implementation already exists; read-only inspection and 12 focused test files (85 passed) verify local cache/shell contracts. No code change was necessary. The task remains open because current remote PR/commit state and the warmed-deployment navigation, polling, and role-freshness drill were not available. See `task-T11-verification-report.md`.

Task 10 (T10): complete locally after initial scoped review and full-scope follow-up review PASS. A fresh repository mypy run dropped from 16 errors to 3: all 13 T10-owned diagnostics were resolved across integration-wave, read-budget, and release-operation tests. Focused tests: 52 passed, Ruff passed, independent reviewer reproduced the same three remaining T02/T32-reserved read-path errors. The T07-owned PyYAML import diagnostic has a separate reviewed follow-up fix. See `task-T10-report.md`, `task-T10-fullscope-followup-brief.md`, and review artifacts.

T13 source-of-truth correction: the authoritative C3 row now matches the approved execution plan: deterministic request-waterfall checks in PR CI and a pinned warmed-stack timing probe in release evidence, with no wall-clock PR gate. Independent review PASS; C3 stays open for actual release evidence. See `task-T13-canonical-acceptance-reconciliation.md` and `task-T13-canonical-acceptance-review.md`.

T15 source-of-truth correction: C6 and its execution packet now distinguish path routes from rendered alignment/RTL states and specify the executable role matrix, direct-member Admin denial, and direct-load deep-link assertion. Two scoped independent review rounds passed; C6 remains open until route E2E evidence exists. See `task-T15-canonical-scope-reconciliation.md` and `task-T15-scope-review.md`.

Task 12 (T12): complete locally after one blocking independent-review finding was fixed and re-reviewed. Shell chrome now stays closed until auth, forced-password, role, and exact manager/admin-tab access are ready; a manager with a stale `ai` tab cannot flash that restricted surface before the tab resets to cycles. All ten requested panels are distinct lazy chunks. Route loading/error/not-found boundaries are correctly placed. Focused Vitest: 39 passed; SPA typecheck/build and manifest checks pass. See `task-T12-report.md` and `task-T12-review.md`.

Current QG-002 result after T07 typing cleanup and T08–T10: the exact full command reports **3 errors in 2 files** (379 source files checked), all reserved for T02/T32: `src/services/supabase_api_mode_read.py:575` plus two `backend_app/read_query_helpers.py` diagnostics. This is distinct from the original 2026-09-23 baseline of 160 and the 2026-09-20 register value of 127.

Task 9 (T09): complete locally after implementation review plus two scoped follow-up review rounds. The nine runtime source files are clean under full-scope mypy; the backup/restore protocols now reflect distinct manager requirements. An explicit falsey restore adapter is selected and validated consistently, with regression coverage. Focused tests: 138 in the initial implementation report; 57 after the protocol/validation follow-ups; Ruff and mypy pass. See `task-T09-report.md`, `task-T09-independent-review.md`, `task-T09-provider-protocol-followup-review.md`, and `task-T09-provider-protocol-followup-rereview.md`.

Ruling: re-scope T04 to verification/disposition because signed canonical A3 is Done: `phase-1-evidence` already gates production approval and the PR pytest suite already exercises verifier fixtures. F6 stays blocked on real provider/owner/approval evidence; a failing honest bundle is the intended gate result. Cost if wrong: a real A3 wiring regression could be overlooked; T04 therefore checks the current workflow and `tests/test_phase1_promotion_gate.py` and reports any exact mismatch for a scoped plan update. This narrows downstream work and does not alter the earlier local T00/T01 cross-signoff; it does not claim current remote CI, a merged change, or provider evidence.

Ruling: reconcile F8 after T07's scoped re-review PASS as **done locally for inventory and deterministic repository gating**. The initial 25 unenforced candidates now resolve to two unconditional `repository-readiness` PR gates required by `ci-result`, seven actual imported/executed helpers, and sixteen operator/developer commands without direct invocation in the three enforcement surfaces or Python helper imports; the four admin CLIs among those sixteen are source-read by `verify_admin_process_contract.py`, not imported or invoked. All 25 have a disposition, and none was proven dead. Cost if wrong: calling the operator commands dead could remove needed recovery tools, while calling static CI checks live evidence could falsely close provider, topology, or restoration gates. Preserve those external evidence and owner gates and do not infer a hosted CI run. This is a canonical F8 row correction only; the coordinator owns the T07 checklist state.

Task 17 (T17): D6-1 complete locally after independent review PASS. A correctly signed Python-format token is rejected by BFF while the native BFF token positive control succeeds; Python issuer/verifier are documented as deprecated and non-authoritative, with formula/types unchanged. Focused Python (13), BFF (9), and typecheck pass. D6-4 deletion remains gated on external-consumer evidence. A separate T15 E2E run revealed that `server.ts` maps backend `GET /v1/auth/me` 429/5xx responses to `SESSION_REVOKED` and clears cookies. The T17 follow-up brief authorizes only typed status distinction and regression coverage: explicit 401/403 rejection clears; transient throttling/server failure stays fail-closed and preserves cookies. See `task-T17-non-auth-status-followup-brief.md` and the T15 diagnostic excerpts.

Task 6 (T06): complete locally after independent review PASS. Genuine fresh clone at the exact workspace baseline integrated Fastify 5.12.5 through npm into `spa-bff/package.json` and both npm lockfiles; changes were copied byte-for-byte by SHA-256. Two separate full clean clones passed `npm ci`, audits (0 vulnerabilities), 320 workspace tests, build, and typecheck. Shared working copy has the reviewed three-file change but no Git commit/push; see `task-T06-report.md` and `task-T06-review.md`.
T18 preparation: `task-T18-brief.md` records the isolated verifier scope, security acceptance tests, and hard T06 dependency; no route, package, or lockfile edits were made.

T19 preparation: read-only recon confirms no current target identity facts; the historic D8 database count cannot authorize an account-link schema. 	ask-T19-brief.md records a verified (iss, sub) fail-closed contract and explicit production prerequisites. No database was queried and no production integration was attempted.


Ruling: T02 non-admin task visibility is goal-owner-in-scope OR task-assignee-in-scope; the assignee case remains visible even when the parent goal owner is out of scope. This follows the existing TCP predicate and the packet's explicit parity criterion. Evaluation failures return a controlled explicit error rather than silently losing rows; raw exception text must not be exposed. Cost if wrong: assigned task data may cross parent-goal ownership boundaries, or authorized work may be hidden. The exact contract and cases are in `task-T02-brief.md`.
Task 33 (T33): complete locally after independent review PASS. The SPA relay forwards edge-supplied `X-OKR-Client-IP`, preserves absence, and excludes inbound XFF/X-Real-IP. Focused Vitest: 8 passed; SPA typecheck passed. The test explicitly does not prove header provenance, edge overwrite, or direct-BFF reachability; T31 retains those deployed-edge gates. See `task-T33-report.md` and `task-T33-review.md`.
Task 16 (T16): partial after independent review PASS. Digest-pinned BFF image record reports Node 22.23.2; CI specifies only Node 22, so no exact hosted patch is available and `engines.node` remains unchanged. ESLint reports 0 errors and the same 9 warnings; all are documented, with no suppressions. Both SPA and BFF typechecks pass. C4 remains open for exact runtime evidence and the deferred F3 UI decisions. See `task-T16-report.md`, `task-T16-snapshot.md`, and `task-T16-review.md`.

Ruling: extend T15 with one narrow backend support fix at `backend_app/read_query_helpers.py:1247`, after Phase 1 proved `alignments.context` calls nonexistent `main._enum_value` and the fixture's real edge serializes correctly through `src.serialization_helpers._enum_value`. The fix is isolated to this helper and a regression test, before T32 reserves the file's separate budget slice. Cost if wrong: touching a shared read helper could change unrelated serialization; regression coverage pins the exact endpoint and edge payload.
Ruling: extend T15 with a second narrow backend support fix at `backend_app/read_query_helpers.py:910`, after the full browser suite showed Work History stuck loading and direct reproduction against its isolated SQLite database proved `getattr(..., main.datetime.min)` eagerly dereferences nonexistent `backend_app.main.datetime`. The fix is limited to a safe sort fallback and a real authenticated `work_logs.by_task` regression, before T32 reserves this helper. Cost if wrong: changing read ordering could affect the Work History display; the test pins returned rows and descending `start_time` order.
Ruling: authorize T27 to harden `execution.observed_at` as a timezone-aware ISO-8601 timestamp and pin the existing `.execution = $execution` workflow attachment. Read-only inspection proved the workflow already calls the strict verifier with `--record`, while malformed observation timestamps currently pass. Cost if wrong: valid provider records could be rejected or workflow wiring may change; preserve the valid UTC case and use only the existing generic path. This does not claim the live paired rollback rehearsal.

Task 27 (T27): PASS locally after independent review. The reviewer requested explicit coverage for a missing `execution.observed_at`; a parameterized missing-field case now pins the verifier's existing rejection. The final focused verifier and wiring suite passes 55 tests. The provider-backed paired rollback rehearsal remains open.

Task 26 (T26): PASS locally after independent review. The actual FastAPI runtime test proves operator state files are not exposed through the API even if the state-path variable is injected; inventory is empty/404, lifecycle POST is absent, operator/customer boundaries and SQL rollout route remain. The full OpenAPI/generated schema/operation contract chain was regenerated and checked. Operator CLI explicit-file persistence remains intact.

T13 gate refresh (2026-09-23): GitHub read-only metadata confirms PR #177 is closed/merged at `3e35315c5ee9d21c7605e6f88a97d148ad3e1050`; the warmed C8 drill remains unverified. The plan has no approved frontend page target or aggregation formula. T13 will implement deterministic request assertions and a protected measurement-only browser artifact that reports `score_status=unscored`; no API SLO is borrowed and C3 remains open until owner approval plus a successful warmed-stack artifact.

Environment gate probe (2026-09-23): `OKR_TEST_POSTGRES_URL` and `OKR_TEST_PGBOUNCER_URL` are both absent from this process environment (presence only was checked; values were not read into output). T32/T35 topology acceptance cannot run in this checkout until real test DSNs/services are supplied; no SQLite/mock substitute will be used.
Task 6 (T06): complete locally after independent review PASS. Genuine fresh clone at the exact workspace baseline integrated Fastify 5.12.5 through npm into `spa-bff/package.json` and both npm lockfiles; changes were copied byte-for-byte by SHA-256. Two separate full clean clones passed `npm ci`, audits (0 vulnerabilities), 320 workspace tests, build, and typecheck. Shared working copy has the reviewed three-file change but no Git commit/push; see `task-T06-report.md` and `task-T06-review.md`.
Task 15 (T15): PASS locally after independent review. The opted-in module passed **6/6 twice**: implementer run 124.24s and independent reviewer run 234.95s. The focused role-route test passed 1/1, all roles rendered dashboard/daily/timeline/retrobox and met role-specific Admin assertions; deep-link reload, alignment, and RTL assertions passed. Two narrow backend read defects were fixed test-first with 25 focused regression/support tests. T15 sets `OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS=10000` only in its isolated fixture because all simulated users share loopback IP; this is not production rate-limit evidence. BFF 429 handling is fixed and independently reviewed under T17. Logs had no 429/session revocation, and fixture listeners exited. Ruff, py_compile, and independent review pass. See the T15 task artifacts.

## Safe pause checkpoint (2026-09-23)

The user requested a safe stop after documenting work. No further development or test runs are authorized until the user resumes. The active T13 implementation/review agents were interrupted at this checkpoint.

- Completed locally and independently reviewed: T02–T10, T12, T15, T17 follow-up, T18 isolated verifier, T26, T27, and T33, as detailed in the packet rows and task reports above. This records local implementation evidence only; all previously stated external/provider/owner gates remain open.
- T13 is in progress, not complete. The canonical C3 decision and acceptance reconciliation are reviewed. The CI workflow classifier now includes the browser E2E test path, and `tests/test_spa_waterfall_ci_wiring.py` exists; its verification status at pause is not confirmed. A report-only frontend probe, schema tests, docs, and protected prerelease workflow wiring are present in the working tree; the probe/workflow chain has not received final integration review or a complete run. No warmed-stack artifact exists, and C3/C8 remain open.
- The attempted T13 browser run failed before navigation with connection refusal / conflicting Next dev server state. Follow-up observed listeners on ports 63094 (PID 30504) and 56741 (PID 24416), believed to be stale Next/BFF processes from the test attempts. An elevated process/listener ownership query was denied by the environment, so no process was stopped and no lock file was removed. The browser waterfall test has not passed.
- T14 API implementation remains paused pending the user's answer on current-password policy. T11 C8, T13 C3, T16 exact-hosted-Node/deferred-decision items, T17 external consumer evidence, T27 live provider rehearsal, T19–T25 owner/customer/identity gates, T28–T31 provider/deployment/edge gates, and T32/T35 database service/DSN gates remain open as described above.
- Git status was inspected. The worktree contains many modified and untracked files across the authorized packet work. The branch is `SPA-BFF-clean` tracking `origin/SPA-BFF-clean`; remote is `origin` (`https://github.com/FaraatarTID/okr.git`). Git emitted access-denied warnings reading the user's global ignore file. Repository metadata is read-only in this environment, so no commit or push was made. No staging was attempted, to avoid capturing changes of uncertain provenance in the shared worktree.
- Resume point: review the T13 waterfall/probe artifacts, resolve the test-server isolation issue with verified test-owned process state, finish local deterministic checks and independent review, then update the T13 row. Do not claim a warmed-stack result without the protected release run and artifact.

## Resume / pause checkpoint (2026-09-23)

The user requested that the execution goal remain paused. T13 work briefly resumed, then stopped at the user's request; both active T13 agents were interrupted. Do not continue implementation, tests, or agent dispatch until the user resumes.

- Additional verification after the prior checkpoint: `.venv\\Scripts\\python.exe -m pytest -q tests/test_spa_waterfall_ci_wiring.py tests/test_prerelease_workflow_contract.py` passed **7 tests** in 0.17s. This covers the CI path classifier and prerelease workflow contract only; it does not prove the browser waterfall, probe execution, or warmed-stack artifact.
- The deterministic browser case is present at `tests/test_e2e_playwright_spa_login_to_atlas.py::test_authenticated_shell_request_waterfall`; a full focused browser run still has not passed. The earlier launch failure/conflicting Next dev-server state and inability to verify elevated process ownership are recorded in the previous checkpoint.
- The report-only probe, probe schema tests, performance documentation, and protected prerelease workflow step/artifact remain in the shared worktree. The resumed probe implementer and waterfall agent were interrupted before a final report/review; their final state and any in-flight edits have not been confirmed. Do not claim T13 complete. C3 and C8 remain open; no warmed-stack result was produced.
- No other packet was advanced in the resumed interval. No Git staging, commit, or push was performed; `.git` remains read-only as recorded above.
- Resume at T13 by rechecking the current tree and agent/tool state, confirming whether the interrupted files changed, then completing safe test-server isolation and independent implementation review before considering further packets.
