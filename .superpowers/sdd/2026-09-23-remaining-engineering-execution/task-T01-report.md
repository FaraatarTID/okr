Documentation HQ: [README](../../../README.md)

# T01 independent baseline audit — 2026-09-23

**Result: RECONCILIATION REQUIRED. Downstream implementation must not start yet.** The 47 A–F entries are present and generally accurately distinguish local implementation from unverified acceptance. The plan has exactly 32 unique packets, T00–T31, and its principal security gates are explicit. However, T00 and the packet map omit active entries in the canonical register's Phase 1 progress table. The shared-file/interface matrix is incomplete. These are material failures of T01 acceptance (b) and (d), not reasons to discard the valid A–F reconciliation.

This is an independent source and document audit. No production code, canonical register, execution plan, or progress ledger was edited; no Git write, network query, deployment operation, or behavioral test was performed. Only this report was written. Existing historical test/CI claims are identified as historical evidence, not independently repeated results. Source presence does not certify behavior, merge, required CI, or a live drill.

## Sources and verification method

References below use `R` for `docs/REMAINING_ENGINEERING_PLAN.md`, `P` for `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md`, and `L` for `.superpowers/sdd/2026-09-23-remaining-engineering-execution/progress.md`. Line numbers refer to the files read during this audit. T00 is the sibling `task-T00-report.md`.

Read the T01 brief, all register issue/progress tables and surrounding sequencing/acceptance notes, the full execution plan, T00, and the full ledger. Used `rg` to inspect the cited implementations, tests, configuration, workflow invocation/dependency chains, and absent route/caller surfaces. Read-only `git status --short` and the scoped register diff confirmed that the only register edit is the F3 preface correction described by T00. Existing `.gitignore`, README, and execution artifacts remain present. Git reported an inaccessible user-global ignore file; no Git writes were attempted.

Independent structural inspection with Python `pathlib`/`re` produced:

```text
report_rows: 47; report_unique: 47
packet_rows: 32; packet_unique: 32; packet_missing: []
self_rows: 32; self_unique: 32
T00 explicit repository paths: 64; missing: []
```

The path check covers explicit repository-relative paths in the 47 T00 rows. Abbreviated basenames were resolved separately: `cycles.ts` and `adminResources.ts` are under `spa-web/src/lib/`; `rollback-execution-verification.yml` is under `.github/workflows/`. A preliminary search under `spa-web/src/lib/api/` found neither cache wrapper; that search location was corrected, and is not a missing-file finding.

The completed report's own structural check found 47 A–F audit rows, 32 packet self-audit rows, no CR bytes, no trailing whitespace, a final newline, and an existing Documentation HQ link target. These are document checks, not behavioral tests.

## Discrepancies and smallest corrections

| ID | Severity | Exact evidence | Finding and smallest correction |
|---|---|---|---|
| T01-1 | High, baseline blocker | R:231–237; P:31–46,52–84; T00 item table and its duplicate-F note | Active P0-2, P0-3, P0-4 remainders, P0-5, and P0-8 have no explicit T00 reconciliation or register-to-packet mapping. Add these progress rows to T00 and map their remaining work into existing packets as described below. Preserve 32 packet IDs. Record closed P0-1/P0-6/P0-7 as baseline history as well. |
| T01-2 | Medium, baseline blocker | L:13–24 and133 versus P:23,38–84 | Matrix covers broad lanes but omits concrete cross-lane file/interface edges; the claim that it maps shared files/contracts is not complete. Add the explicit edges below, assign concrete file ownership in task briefs, and retain serial integration. Directory separation among T08–T10 does not establish separation from other packets. |
| T01-3 | Medium, reconcile before T19 | R:113 versus P:67 and L:119 | Register says to re-run provisioning counts **before implementing** and confirm the target deployment invariant. T19 only explicitly requires target verification **before enabling**. The subordinate plan must retain the earlier register gate, or cite an authorized revision. Smallest correction: say that target counts/provisioning verification precede implementing the chosen production integration; keep fixture/design preparation clearly distinguished. |
| T01-4 | Medium, document truth | R:10–15 versus R:436–440; P:21 | The canonical register calls itself current authority and the architecture-status ledger historical, but its later Status tracking section still directs every item into that historical ledger. P correctly follows the opening authority rule. T00 does not flag the internal contradiction despite auditing the register. Smallest correction: reconcile that stale Status tracking paragraph to the current A–F/P0 status rule without rewriting historical rows. |
| T01-5 | Low, current evidence precision | R:222 versus `.github/workflows/ci.yml:118,172–173,614–645`; T00 B5 | Historical B5 progress says `postgrest-exposure-gate` is the job ID in `ci-result`. The current invocation is the named **PostgREST Exposure Gate step inside `migration-quality`**, and `ci-result` depends on `migration-quality`. The control still exists, but the historical job wiring is not current. Record that distinction; do not claim present branch protection references from the old row. |
| T01-6 | Low, status precision | L:29 and89–94; P:101 | Checklist leaves T00 unchecked while prose says complete. The plan's global closure rule requires merge and required CI; neither can be established here. Use a precise local outcome such as `reconciled/reviewed locally; integration pending`, distinguish it from canonical CLOSED, and update the checkbox consistently after T01 corrections. |

Additional bounded clarification: T00 E3 calls a code remainder open, while `.github/workflows/rollback-execution-verification.yml:61–84` already attaches `.execution` and invokes the strict `--record` path, and `tests/test_rollback_workflow_wiring.py:188` checks a record invocation. That supports “repository path exists; acceptance needs checking,” not an assumption that it must be built from scratch. R:148 still cites the older Darkube manual-input context. T27 should first identify whether a specific Darkube path remains missing or the current generic production workflow already satisfies the repository portion, then implement only an evidenced gap. Live rehearsal stays blocked either way.

## All 47 A–F entries and packet mappings

“Matches” below means the T00 local-state characterization is supported by the cited source. It does not turn source inspection into execution evidence. All rows additionally map to T00/T01 baseline reconciliation. A dash in the implementation-packet column means a landed historical item needs no new implementation packet.

| Item | Register source | Independent checkout evidence / disposition | Implementation packet |
|---|---|---|---|
| A1 | R:61,215 | Matches landed source: `scripts/deploy_saas_release.py:10` has the package bootstrap; `tests/test_cli_entrypoint_bootstrap.py:72` creates an unrelated directory. Subprocess acceptance not rerun. | — |
| A2 | R:62,216 | Matches: `scripts/restore_saas_environment.py:43,62–63` registers through shared validation; `src/saas/backup_operations.py:131,265,683` validates both paths; `tests/test_saas_backup_operations.py:581,666` contains round-trip/unsafe-target cases. | — |
| A3 | R:63,226 | Matches local placement: `promote-production.yml:118,140,145` runs the bundle check and makes approval depend on it; `ci.yml:349` runs verifier fixtures through pytest. Production bundle remains blocked. | T04 |
| A4 | R:64 | Matches open: `backend_app/main.py:400` constructs `ControlPlane()`; `scripts/verify_process_contract.py:37` rejects runtime state-path templates. `tests/test_control_plane_stateless_runtime.py:11,32–35` proves separate source contracts exist, not that all API/document acceptance is reconciled. | T26 |
| A5 | R:65,219,229 | Matches with A6c supersession: `scripts/verify_recovery_evidence.py:109` invokes real shared verification; `scripts/attestation_verification.py:207` verifies configured signatures; forged-recovery test at `tests/test_recovery_evidence.py:196`. Rollback's later Cosign-only contract supersedes the original “both verifiers” wording. | — |
| A6 | R:66,227–229 | Matches current local result: `rollback-production.yml:95,164` supplies verified Cosign references; preflight uses `--approval` at 198; execution workflow uses `--record` at 81. T00 does not infer remote secret or live rollback state. A6c removes the obsolete manifest HMAC; preserve that precedence. | T27 covers E3 remainder |
| B1 | R:72,220 | Matches: doc example and `tests/test_documented_evidence_schema.py:83,102,111,121` cover schema, renamed key, key material, and Phase1 fields. No test rerun. | — |
| B2 | R:73 | Matches open: `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md:54` still says remaining blockers are operational, not repository gaps. | T05 |
| B3 | R:74,221 | Matches corrected distinction: `docs/bff-boundary-adr.md:44–52`, `docs/security/rate-limit.json:8–9`, `docs/evidence/security-parity.json:16,40` retain pending missing controls; `spa-bff/src/config.ts:19` is 20,000 ms. D4 remains open. | —; D4→T24 |
| B4 | R:75 | Matches open: backlog:15 says superseded, while :188 still claims a production readiness performance probe. | T05, with T13 dependency |
| B5 | R:76,222 | Local checker and invocation exist; current job is `migration-quality`, not historical `postgrest-exposure-gate`. See T01-5. `scripts/check_rls_enabled.py:4–10` explains exposure versus tenancy. | — |
| B6 | R:77,218 | Matches: `docs/QUALITY_GATE_BASELINE.md:17,23,25–37` closes QG-001, records QG-002 expiry 2026-11-15 and milestones. Expiry disposition is landed; debt is still open. | T08–T10 via QG-002 |
| B7 | R:78,223 | Matches historical cleanup: `docs/WORKLOG.md:613,622` contains explicitly reconstructed entries. Current `git status` has none of the old SaaS code files modified; today's authored execution docs remain modified/untracked. | — |
| B8 | R:79,224 | Matches: `AdminModePanel.tsx` tab definition has no security member; searches of frontend implementation/config docs find no removed AI-sync variables/helper; Ritual panel has no dead `rtlStyle` import. | — |
| C1 | R:89,283–285 | Matches implemented subset/open drill: `resourceCache.ts:27,76–85,144` implements 60s caching/clear; `cycles.ts` and `adminResources.ts` import it; `useAdminActions.ts:182` clears before restore reload and mutation reloads bypass cache. Tests cover TTL/dedupe/rejections/clear. No session cache inferred. | T11 |
| C2 | R:90,301 | Matches open: complete `spa-web/src/app` file inventory has no `loading.tsx`, `error.tsx`, or `not-found.tsx`; shell panel streaming not established. | T12 |
| C3 | R:91,265–270,301 | Matches open: backlog probe claim persists; no required SPA page-load budget was found in CI/justfile. Existing backend hotpath tests do not close SPA budget acceptance. | T13 |
| C4 | R:92,287–291,294,300 | Matches gate landed/follow-ups open: root lint/typecheck scripts and BFF typecheck exist; BFF build config has `incremental:false`; runtime engines still need exact image observation, and eight lint findings are recorded, not independently rerun. | T16; QG scope remains T08–T10 |
| C5 | R:93,301 | Matches open: `login/page.tsx:130` mounts PasswordChangePanel; search finds no signed-in entrypoint. | T14 |
| C6 | R:94,301 | Matches open: `tests/test_e2e_playwright_spa_login_to_atlas.py:856–907` parametrizes three roles and exercises existing timer/check-in/weekly/admin cycle/sign-out paths; omitted routes remain unclaimed. | T15 |
| C7 | R:95,225,289 | Matches local fix: `spa-bff/vitest.config.ts:22` excludes dist; `tsconfig.build.json` emits source only. Historical planted-file 9/74 run is not rerun. | — |
| C8 | R:96,286 | Matches implementation/open verification: `(shell)/layout.tsx` owns AtlasShell and children; route ownership/layout tests exist. Current PR #177 state and warmed navigation/polling drill remain unverified. | T11 |
| C9 | R:97,217 | Matches: `useShellAccessControl.ts:61–66` resolves forced-password-change before ordinary chrome gates; focused tests exist. | — |
| D1 | R:101–106,325 | Matches not started: Python carries discovery `jwks_uri`; `identity_ports.py:97,103,207` trusts supplied signature-validity state. No BFF verifier found. No JOSE dependency in current BFF manifest. | T18 |
| D2 | R:107,308–313,325 | Matches not started: `server.ts:321,435,490` exposes login/me/logout; SPA session files contain only those three passthroughs. No OIDC authorize/callback route found. | T24 jointly with D4 |
| D3 | R:108,322,326 | Matches D3a-only landed: `session.ts:21` in-process map, :170 unknown-record path; repeated replay tests in `session_revocation_replay.test.ts:127,182,205`. `normalizeSessionUser` omits external subject; no production `revokeSessionsForIdentity` caller found. Cross-instance/store/unknown-SID requirements stay open. | T22→T23 |
| D4 | R:109,324 | Matches not started: `server.ts:256` hook exists, but no origin/limiter enforcement found in BFF source; catch-all CSRF test does not cover native login/logout/OIDC. Coupled integration gate explicit. | T24 |
| D5 | R:110,325 | Matches open/not started, conditional scheduling: `identity_ports.py` imported only by its test; `entitlement_policy.py:26,73` disables enforcement. Customer/owner trigger is not supplied locally. | T25 |
| D6 | R:111,116–137,319 | Matches decision versus implementation: `identity_contract.py:457,503` retains Python pair; BFF session format differs. No external-consumer finding can be certified locally. | T17 |
| D7 | R:112,325 | Matches open: BFF freezes and forwards version (`server.ts:178,201–202,594–595`); `backend_app/security.py:296` resolves scope without it. | T21 |
| D8 | R:113,320 | Matches blocked target/integration: `src/models.py:125–155` has username/token_version but no identity link; `platform_routes.py` resolves username. No external-subject/enterprise-exchange migration or route found under `alembic/versions`/`backend_app/routers`. Historical database counts are not current target facts. T19 timing discrepancy is T01-3. | T19 |
| D9 | R:114,321 | Matches open/human fact missing: `identity_contract.py:436` coerces the claim using `bool(...)` rather than requiring boolean true, then copies it at 487. Selected IdP guarantee remains unknown. | T20 |
| D10 | R:323 | Matches open: version is read by platform auth/me and two AI endpoints (`platform_routes.py:138–149`; `ai_routes.py:165–173,192–201`); other scope calls omit it. Forwarding tests do not establish full enforcement. | T21 |
| E1 | R:146 | Matches blocked: local provider and entry-evidence `UNSELECTED` do not supply real provider contract or operation IDs. | T28 |
| E2 | R:147 | Matches blocked: `release_operations.py:106,122–123` protocol/local-only adapter, `deploy_saas_release.py:16,78` imports/constructs it. No live adapter found. | T29 |
| E3 | R:148,227–229 | Live drill blocked; existing execution workflow already writes `.execution` and reaches strict record verifier. Repository remainder needs precise reconciliation before writing code; see bounded clarification above. | T27 |
| E4 | R:149,414 | Matches deferred scheduling/target inputs absent. Both backend deployment YAMLs contain `REPLACE_WITH_RELEASE_DIGEST`; no SPA/BFF manifest exists. Register calls it code/low priority rather than external-only. Plan may gate scheduling, but preserve that distinction. | T30 |
| E5 | R:150 | Matches blocked: `phase-1-entry-evidence.md:64,66` has UNASSIGNED/false, `release-signoff.md:10,48–50` unassigned owner/unselected provider IDs. | T31 |
| E6 | R:151,414–415 | Matches explicit deferred scope; no local fact can supply owner scheduling decision. | T31 |
| F1 | R:183 | Matches guard landed/parity open: `_validate_read_scope` at `read_query_helpers.py:216` runs before dispatch; literal six-kind parity acceptance remains open. P0-2 makes the task-row distinction especially material. | T02 |
| F2 | R:184 | Matches helper landed/boundary audit open: `crud_query_helpers.py:90–94` rejects unscoped found nodes; `tests/test_crud_authorization.py:530` asserts rejection. The register says “six” once while enumerating seven; T03 must cover all seven listed kinds. | T03 |
| F3 | R:185 | Matches specific filters landed: HTTPS cycle filter at `read_query_helpers.py:302,545`; goal helper and needing-checkin/retro branches in `supabase_api_mode_read.py:54,732,874`. Do not interpret this as F1 combined parity or P0-2 assignee parity being closed. | T02 verifies closure |
| F4 | R:186 | Matches: `supabase_api_mode_read.py:503,572` calls `_allowed_goal_ids_for_cycle` for by-cycle queries; focused read tests exist. | — |
| F5 | R:296 | Matches local dependency/block: manifest `^5.6.1`; root lock:5642 and BFF lock:1388 pin 5.8.5. T00 correctly avoids treating historical registry/advisory assertions as current. No genuine fresh-clone verification occurred. | T06 |
| F6 | R:297,226 | Matches blocked production facts/local placement: promotion check exists and real bundle remains BLOCKED. R:297 “not wired into CI” must be read alongside the later promotion-placement evidence; ordinary PRs intentionally use fixtures. | T04 |
| F7 | R:298 | Matches historical local generated-artifact repair: web typecheck script and SPA Web CI step exist. Present `.next` repair/remote CI not certified by this audit. | — |
| F8 | R:299 | Matches open: observability/release-pair scripts exist and neither is referenced by workflows/justfile/pre-commit. T00 accurately labels the 25/14 inventory historical; current full classification belongs to T07. | T07 |

The second Phase2 F1–F4 namespace (R:292–295) is separate: timeout abort behavior, proxy log redaction, lint triage, and Windows npm launcher. T00 acknowledges that collision. The implementations are present in `spa-web/src/lib/api/http.ts`, `spa-web/src/lib/bff-proxy.ts`, ESLint targets, and `scripts/verify_dependency_scans.py`; remaining lint triage maps to T16. Use labels such as `Phase2 progress F3` versus `Read-path F3`, not an ambiguous F3 alone.

## Omitted active progress rows and acceptance

These are **active status rows**, not historical ledger IDs to ignore. R:10–15 makes this file current authority and explicitly labels only `docs/architecture-status.md` historical. R:230–237 is within **Phase1 / Progress**, with P0-2, P0-3, P0-5, and P0-8 literally marked Open. P0-4 explicitly enumerates unfinished work despite the first status phrase. None is under Out of scope. The execution plan's goal P:11 is completing remaining canonical work; restricting T00 to 47 A–F IDs silently loses these rows.

| Row | Exact remaining contract and dependencies | Independent local evidence | Minimal mapping amendment, preserving 32 packets |
|---|---|---|---|
| P0-2, R:231 | Decide the correct task visibility predicate across TCP/HTTPS; TCP admits goal ownership **or assignee**, HTTPS admits owning goal only. Remove the broad exception path that silently drops a task. Row says this is intentionally not fixed because it changes visibility and depends on the path-parity decision. It has no separately tabulated numerical acceptance threshold. | `backend_app/response_scope_helpers.py:469,485–494` contains assignee inclusion and `except Exception: continue`; `src/services/supabase_api_mode_read.py:572` filters by permitted goals. | Add explicit P0-2 subdeliverable to T02. Cover assigned-in-scope/on-out-of-scope-goal rows and malformed task handling, settle/document the visibility predicate before changing it. Do not infer the product decision from F3's historical closure. |
| P0-3, R:232 | Measure `ritual.snapshot` amplification on PostgreSQL; do not assume P0-1 cache collapses it. SQLite lacks `fn_ritual_snapshot` and its fallback returns 500, so a PostgreSQL-backed fixture is required. No self-skipping “coverage.” Record measured scope resolution/statement/connection effects rather than repeating static 7–8 estimates as runtime facts. | Snapshot branch/fan-out remains in `backend_app/read_query_helpers.py`; `tests/test_read_path_budget_postgres.py` contains budget counters but no `ritual.snapshot` case (exact search). | Add explicit PostgreSQL snapshot subdeliverable to T13, with backend budget harness files in its ownership/lane. |
| P0-4, R:233 | Two explicit residuals: a spa-web→BFF trusted-client-IP boundary test, and external proof that BFF can only be reached through the edge which overwrites the private header. Trust ADR decision is already made; deployment proof must not be replaced by CI. | `spa-web/src/lib/bff-proxy.ts:98` forwards `x-okr-client-ip`; all five `bff-proxy.test.ts` cases (:35,44,61,72,83) cover response/logging, not header forwarding. | Add boundary test to T24, explicitly before relying on trusted IP for auth limiter; add deployed edge reachability evidence gate to T31. Keep both statuses separate. |
| P0-5, R:234 | Only caller-less identity controls remain open: `revokeSessionsForIdentity` and `src/saas/identity_ports.py`. All other listed sweep members are closed. The Python-only/no-declarative/no-negative-assertion review limits are expressly **not** demands for an exhaustive audit. D3a and P0-6 are separate scope. | Search of src/backend_app/scripts/tests/BFF source/tests finds the TS function only in session implementation and its dedicated test; Python port module only in its test. | Explicit alias to T23 for production revocation reachability and T25 for customer-gated identity ports. D3 owner choice and D5 customer gate remain; no speculative SCIM expansion. |
| P0-8, R:237 | Keep `OKR_DB_USE_NULL_POOL` default true until verification against **PgBouncer transaction pooling**. Stand a pooler before PostgreSQL and run read-budget harness with recorded before/after values. Driver-guaranteed no automatic prepared statements is not an application control; session state/server cursors are distinct risks. Direct PostgreSQL CI is insufficient. | `src/database.py:176` defaults true; `tests/test_read_path_budget_postgres.py:236–249` covers current driver/cursor/pooling behavior; The harness explicitly excludes PgBouncer safety verification; no PgBouncer-backed execution or CI service topology was found. | Add separate PgBouncer subdeliverable/gate to T13, keeping existing default and requiring topology evidence before any default change. It can remain blocked if the pooler runtime is unavailable. |

P0-1 (R:230), P0-6 (R:235), P0-7 (R:236) are marked Done and need reconciliation entries, not new implementation by default. P0-1's SQLite versus PostgreSQL measurements and P0-6's trust dependency must remain qualified. No current test execution or deployment proof was inferred from those rows.

## Hard-gate audit

| Gate | Result / exact evidence |
|---|---|
| D1 before login | PASS as a plan constraint. R:101–106,308–309; P:66,89,99 explicitly prevent real OIDC exposure before signature verification. D1 remains unimplemented locally. |
| D2+D4 atomic | PASS as a plan constraint. P:72,89 requires one branch/review/merge unit and exact OIDC limiter/origin wiring assertion. Current no-Git fallback needs one indivisible integration/review unit; it cannot provide actual merge evidence. No split D2 release is permitted. |
| D3 owner choice | PASS. P:70–71,88; L:122–123 requires explicit owner acceptance before T23, and forbids token_version being described as per-session/unknown-SID semantics without revised acceptance. No such owner choice is locally evidenced. |
| F5 fresh clone | PASS requirement, execution BLOCKED. P:22,42,91 and L:106 require a genuine fresh full clone plus unrelated clean verification, serialize lockfiles, prohibit hand edits/repeated stale retry. Current checkout does not satisfy it. |
| F8 fixtures and wiring | PASS requirement, implementation OPEN. P:43,92 requires positive/negative inputs and proof that workflow invocation runs, with module invocation for package scripts. Two sampled uninvoked validators confirm the task remains meaningful. |
| D6/D8/D9 before D2 | Ordered correctly in P:65–72 and inherited R:311–313; D8's earlier target-count gate needs T01-3 correction. External consumer/client/IdP questions are not answered by ordering packets. |
| D1 algorithm details | P:66 defers exact algorithm/skew details to canonical acceptance via P:97. Dispatch brief must retain RS256/ES256/PS256 only, reject none/all HS,60-second skew, constant-time nonce, TTL cache and one refresh from R:106. No missing implementation is counted as a plan failure. |
| D2/D3 remaining details | Canonical R:107–108,458–459 still controls distinct failure responses, browser-bound single-use state, PKCE verifier protection against stolen-cookie-only recovery, no open redirect, deprovision admin+CSRF/S2S routes, and legacy cutover. Short packet summaries do not supersede these. |

## Pair/interface matrix audit

Existing rows L:12–24 cover useful broad lanes, and the serial fallback lowers simultaneous-edit risk. They do **not** prove a complete pairwise scan. Add the following edges/ownership controls before dispatch. “Scope intersection” here identifies overlapping assigned directories or contracts; it does not claim two unimplemented tasks have already edited the same file.

| Missing edge/group | Concrete shared file/interface | Required control |
|---|---|---|
| T05↔T13 | `docs/architecture/ARCHITECTURE_BACKLOG.md:188`: T05 corrects its probe claim; T13 supplies performance DoD/evidence. | Order the wording change and budget implementation, then reconcile the claim against real enforcement. |
| T13↔T11/T12/T15 | Cache/waterfall contracts in `spa-web/src/lib/resourceCache.ts`, cycle wrappers, shell bootstrap hooks, and `tests/test_e2e_playwright_spa_login_to_atlas.py`. T13 is absent from the frontend lane. | Add performance packet to frontend test/data contracts lane; budget evidence must use final cache/navigation behavior. |
| T16↔T11/T12/T14/T15 | Recorded eight findings include `AtlasShell.tsx`, `InspectorAlignmentPanel.tsx`, `useAdminActions.ts`, `useInspectorAuxData.ts`; these overlap shell/panel/password/E2E surfaces. | Add T16 to frontend lane. Explicitly assign warning dispositions before concurrent refactoring. |
| T23↔T19/T24/T18/T20 | `spa-bff/src/session.ts`, `spa-bff/src/server.ts:151–190`, backend user/identity response, generated session schema; revocation can make session reading async. Current identity rows split these into separate groups without this cross-edge. | Include T23 in the shared auth/API lane; synchronize user shape, new backend routes, async callers and their tests before T24 integration. |
| T26↔T19/T23 | Backend route changes can share `backend_app/main.py`, router/schema wiring, exported OpenAPI and generated clients/allowlist/auth matrix. P:23 applies to every changed backend route, not only enterprise identity. | Add conditional shared-artifact reservation for T26; first decide if stateless surface change affects routes/schema. |
| T24/T30↔T04/T07/T13/T27 | T24 requires CI/release exposure gating; T30 requires rendered-manifest CI validation; both can change `.github/workflows/ci.yml` or release workflows and workflow tests. | Include both in workflow integration lane, even if T30 stays blocked. |
| T08↔T02/T03/T19/T21/T23/T26 | T08 owns unspecified `backend_app` typing files; other packets own read helpers, security, routers and runtime contract in that directory. | Assign exact debt files first, then record actual collisions; “disjoint directories” only describes T08 versus T09/T10. |
| T09↔T02/T03/T17/T19/T23 | T09 owns unspecified `src` typing files; read/service helpers, Python issuer, models and revocation implementation occupy that tree. | Same concrete-file reservation before dispatch. |
| T10↔all test/script authors, especially T02/T03/T04/T07/T13/T18–T24/T26/T27 | T10 owns unspecified `tests`/`scripts`; other packets add/change their focused tests and validators there. | Identify assigned mypy files and serialize any shared test/script edit. No broad claim of disjointness is presently verifiable. |
| All doc-producing packets↔register/quality baseline steward | `docs/REMAINING_ENGINEERING_PLAN.md`, potentially `docs/QUALITY_GATE_BASELINE.md`; P:20,101 mandates status evidence updates. | One register writer; aggregate QG counts after integrated changes. Existing “self-conflict” row is not pair ownership. |

After the suggested P0 mapping amendments, T13 also needs explicit edges to T02/T03/T08/T09/T10 through `backend_app/read_query_helpers.py`, PostgreSQL budget tests, `src/database.py`, and CI service topology. P0-4 adds the SPA proxy boundary to the T24/frontend overlap. Recompute matrix from amended packet scopes rather than treating this table as a permanent exhaustive allocation.

## Every packet self-consistency row

All 32 self-scan rows exist exactly once (L:100–131). The repeated word “consistent” is a conclusion, not evidence. Independent disposition:

| Packet | Audit disposition |
|---|---|
| T00 | REVISE:47 A–F rows valid baseline, but “every progress note” misses P0 rows and stale current-status instructions. |
| T01 | Consistent read-only task; its acceptance is not passed until corrections/re-review. |
| T02 | REVISE mapping/scope to address P0-2 predicate decision explicitly; F3 historical filters must not imply full parity. |
| T03 | Consistent; cover all seven enumerated kinds despite register's stray “six”; reserve read-path files. |
| T04 | Consistent; source already has promotion placement and pytest fixtures, so first identify any missing wiring acceptance. |
| T05 | Consistent; add T13 documentation edge and canonical status-tracking contradiction disposition. |
| T06 | Consistent but blocked here; genuine clone and independent verification mandatory. |
| T07 | Consistent; current classification/invocation evidence still required, no source-string-only closure. |
| T08 | Conditional: directory scope is clear, concrete file allocation and cross-packet conflicts are not. |
| T09 | Conditional for same reason; counts cannot be integrated independently of ongoing source changes. |
| T10 | Conditional for same reason; tests/scripts overlap practically all behavioral packets. |
| T11 | Consistent; no session cache, actual warmed drill and fresh PR facts remain open. |
| T12 | Consistent; no authenticated fallback before access checks; add T13/T16 edges. |
| T13 | REVISE mapping for omitted P0-3/P0-8 subdeliverables if preserving 32 packets; current frontend budget contract itself is consistent. |
| T14 | Consistent; signed-in success/failure behavior, frontend reservations required. |
| T15 | Consistent; actual visits and isolated data, frontend/performance reservations required. |
| T16 | Consistent runtime observation gate; add concrete frontend/CI edges and preserve unresolved product decisions for lint findings. |
| T17 | Consistent; local consumer search cannot certify consumers outside the repository; deprecate before external-search-gated deletion. |
| T18 | Consistent D1 gate; blocked dependency integration while fresh-clone T06 remains unresolved. |
| T19 | REVISE explicit target-verification timing per T01-3; migration freeze and backfill authorization remain required. |
| T20 | Consistent; missing/false/nonboolean claim rejected; production enablement waits for owner IdP fact. |
| T21 | Consistent; full protected-route matrix and account-wide bound; changes scope-resolution cache/security interface. |
| T22 | Consistent decision packet; no local owner approval inferred. |
| T23 | Consistent conditional implementation; add P0-5 alias and shared schema/async caller edges; preserve deprovision acceptance. |
| T24 | Consistent atomic security constraint; add P0-4 boundary test mapping, shared frontend/CI/API edges, and exact fallback integration-unit handling. |
| T25 | Consistent customer gate; add P0-5 identity-port alias, no scope expansion without trigger. |
| T26 | Consistent selected stateless model; verify actual route impact and reserve API artifacts conditionally. |
| T27 | Conditional: distinguish existing strict execution path from any truly missing Darkube wiring before adding code. |
| T28 | Consistent external provider gate; keep test-only adapters distinct. |
| T29 | Consistent external runtime target gate; local adapter does not deploy. |
| T30 | Consistent deferred target gate; include its future CI lane reservation. |
| T31 | Consistent human gates; add P0-4 deployed-network proof to its explicit map. |

## Facts not independently verifiable locally

| Category | Unverified facts and affected items |
|---|---|
| Remote CI / PR / merge | Current PR #177 review/merge/head and required CI; all historical commit/CI outcomes in A6/A6b/A6c, C7/C8, D3a, P0 rows; current main/publish/promotion/rollback workflow outcomes; required-check and branch-protection configuration after job restructuring. Local source or commit subjects cannot answer these. |
| Secrets / registry / clone | Actual GitHub secret provisioning/removal/access; Cosign identity and verification against published images; current Fastify advisory range/latest supported release and registry resolution; successful unrelated clean-clone install/test/build/typecheck/audit. Local lockfiles only establish currently pinned versions. |
| Provider | Selected Hamravesh/Darkube/other provider, API contracts, provider-issued backup/restore IDs, isolated restore success, measured RPO/RTO, authentic provider attestation/key custody. E1/F6 remain blocked. |
| Deployment / runtime | Real target and runtime adapter contract; exact digest-pinned BFF image Node version and actual CI runtime minor; network edge-only reachability/trusted-header overwriting for P0-4; replica topology and operational limiter capacity; deployment's current database/provisioned accounts; chosen Kubernetes ingress/namespace/secrets/image inputs; availability and fidelity of PgBouncer transaction topology. |
| Identity owner / IdP | Confidential versus public client, issuer/JWKS/client ID/redirect configuration, legitimate-account email and boolean email_verified guarantees; authorized issuer/subject linking/backfill of existing users and no ambiguous links; consumers outside this repo of Python session tokens. R:403–410 explicitly leaves client type and claim guarantee open. |
| Live drills | Actual provider restoration and paired rollback rehearsal; truthful execution outcome supplied to rollback verifier; current warmed-stack shell/session/cycle/team counts and polling behavior; current performance budget; D3 restart/cross-instance/unknown-ID/store-outage drill after an approved design. Existing fixture tests are not these drills. |
| Owner decisions / approvals | Named operations and decision owners; explicit real-data approval; D3 per-session versus account-wide semantics revision; concrete D5 customer demand/owner; deferred E6 scheduling; task visibility semantics if P0-2 requires a product choice. P fixed assumptions record selected implementation direction but do not independently prove who approved an owner-only change. Parent/session authorization may supply facts that are absent from this checkout; do not fabricate them. |

## Release of the baseline gate

Do not dispatch downstream implementation under the current plan. First reconcile T01-1/T01-2, make T19's timing explicit, and disposition the document/status precision findings; record both T00 and independent-review outcomes in the ledger. Keep exactly 32 packet IDs by expanding the named existing packet scopes, or explicitly revise the count if the owner prefers additional packets. Do not silently call 47 A–F entries “all remaining work.”

After that document correction and scoped re-review, repository packets without external gates can begin serially in the current writable checkout with snapshots and review. T06's genuine-clone requirement, T22/T23 owner approval, target/IdP/provider prerequisites, and merge/remote-CI/live-drill closure requirements remain unsatisfied until evidence actually arrives. This audit does not authorize inventing evidence or weakening any canonical acceptance criterion.

## Review correction — 2026-09-23

Corrected the P0-8 evidence sentence: the harness does reference PgBouncer (`tests/test_read_path_budget_postgres.py:218,237,241,289,309`). Lines 241–242 explicitly limit its evidence to a direct connection and exclude transaction-pooling safety verification. The missing evidence is PgBouncer-backed execution/topology, not textual references. Verified the cited lines and report path; no tests were run.
