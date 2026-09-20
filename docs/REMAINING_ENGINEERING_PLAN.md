Documentation HQ: [README](../README.md)

# Remaining Engineering Plan

Status: ACTIVE
Scope: every recognized open engineering issue, its sequencing, and its acceptance test
Companion: [Working Guide](WORKING_GUIDE.md) (how to start work)
Date: 2026-09-19

This is the single register of open engineering work. The
[Enterprise SaaS Roadmap](architecture/ENTERPRISE_SAAS_ROADMAP.md) is the source
of intent, [Architecture Status Ledger](architecture-status.md) is the source of
truth for current state, and this document is the source of sequence.

This plan deliberately separates work an engineer can start today from work that
is blocked outside the repository. Provider-backed backup, measured RPO/RTO, a
live paired rollback rehearsal, a named operations owner, and explicit real-data
approval cannot be closed by writing code. They are recorded in Workstream E so
they are not mistaken for available work.

## Corrections to prior assessments

Three claims made during the repository review of this date are corrected here and
the plan reflects the corrected versions.

1. `docs/architecture/ARCHITECTURE_BACKLOG.md` is not wholesale superseded. Its
   performance package is still open; its tenancy packages are not. B4 splits it
   rather than deleting it.
2. The `rls-gate` CI job is not dead scaffolding. The baseline migration really
   does execute `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`
   (`alembic/versions/baseline_2026_08_26_schema.py:790-795`), and
   `scripts/check_rls_enabled.py` is Supabase/PostgREST exposure hardening, not
   tenant isolation. The check is legitimate and must be kept; only its name and
   documentation are misleading, because ADR-001 rejects shared-database RLS as
   a tenant-isolation model.
3. C8's problem statement said "all nine non-login routes are near-identical
   nine-line wrappers that each render `AtlasShell`". The count was wrong and so
   was the shape. Eight routes rendered the shell, not nine: `app/ritual/page.tsx`
   is a five-line server component that calls `redirect("/check-in")` and renders
   no shell at all. Nor were they near-identical wrappers — they happened to
   converge on the same nine lines only because every one of them duplicated the
   same `<AtlasShell />` call, while `dashboard/page.tsx` was a bare five-line file
   and the `--dashboard` modifier sat on `app/page.tsx` rather than on the route
   that names it. The conclusion C8 draws is unaffected, and the corrected count
   is what the ledger and the worklog record.

## Effort scale

| Size | Meaning |
| --- | --- |
| S | One focused session |
| M | Two to four focused sessions |
| L | Five or more focused sessions |

## Workstream A - Release and recovery integrity

| ID | Issue | Evidence | Deliverable | Acceptance | Size |
| --- | --- | --- | --- | --- | --- |
| A1 | `scripts/deploy_saas_release.py` was missing the interpreter bootstrap guard carried by every other operator CLI. | It is the only one of the five operator CLIs (`provision_`, `backup_`, `restore_`, `migrate_`, `deploy_`) without `if __package__ in {None, ""}: sys.path.insert(...)`; the other four carry it at lines 10-11. Without it the CLI breaks whenever `src` is not already importable, such as a plain interpreter invoked from outside the repository. `uv run` from the repository root **masks** the defect because it makes `src` importable regardless, which is why it survived. Confirmed: with the guard the CLI reaches the argument parser and proceeds to operator resolution instead of failing at import. | Add the guard. | The guard is present, and `python scripts/deploy_saas_release.py --help` reaches the argument parser (exit 0, `usage:` on stdout) from an unrelated working directory. A parametrised subprocess test covers all five operator CLIs. | S |
| A2 | The restore path is unreachable, even with `--test-only`. | `RestoreManager` requires a pre-registered target; `src/saas/backup_operations.py` `register_target` has no non-test caller (only `tests/test_saas_backup_operations.py:152,351,400,411`). The restore CLI exposed `--isolated-target` but no registration path, and `LocalBackupProvider.register_target` did not apply the production-name guard that `RestoreManager._validate_target` applies, so a production-named target could be persisted even though restoring into it would later fail. | Add a `register-target` subcommand to `scripts/restore_saas_environment.py` over the existing `register_target()`, restructured to subcommands like `backup_saas_environment.py`. Extract the target safety check into a shared `validate_restore_target()` used by both registration and restore so an unsafe target cannot be persisted. | A CLI-driven restore into a registered isolated target completes across separate processes. Live and production-named targets are rejected at registration and are not persisted. An unregistered target still fails closed. | S-M |
| A3 | The mandatory Phase 1 promotion gate is never executed by CI. | Zero matches for `saas-evidence` or `check_saas_phase1_evidence` under `.github/`; referenced only at `justfile:45-46`. `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md:190` calls it mandatory. | Wire `just saas-evidence` into CI as a required fail-closed job. Also wire the validators that currently have no CI coverage: `verify_recovery_evidence.py`, `verify_rollback_evidence.py`, `validate_rollback_rehearsal.py`, `verify_release_pair.py`. | CI fails when the evidence bundle regresses. The validator jobs run fixture evidence so both passing and failing inputs are exercised. | S |
| A4 | The control-plane API always serves an empty registry. | `backend_app/main.py:393` constructs `ControlPlane()` with no state path. `scripts/verify_process_contract.py:37` errors if any runtime template sets `OKR_CONTROL_PLANE_STATE_PATH`, and `tests/test_saas_environment_config.py:216` asserts it is absent. Provisioning writes `tmp/saas-control-plane.json`, which the API never reads. | Choose and implement one model: a durable contract-compliant control-plane store the API reads, or a read-only/stateless API surface with lifecycle metadata documented as living only in operator state files. Remove the contradiction either way. | The chosen behaviour is asserted by a test. The process contract check and the environment-config test agree with the documented model. No route returns an environment the operator never recorded, or the surface is explicitly documented as stateless. | M |
| A5 | Attestation verification never verifies the signature. | `scripts/verify_recovery_evidence.py:72-90` and `scripts/verify_rollback_evidence.py:50-72` check only a length floor, an algorithm name, and that `signed_payload_sha256` equals a digest recomputed from the same file, which is self-consistent by construction. | Implement real verification: HMAC-SHA256 through the configured attestation secret for `provider-signed`, and asymmetric verification against a configured public key for `ed25519` and `rsa-pss-sha256`. Reject `provider-signed` when no secret is configured. If asymmetric verification is deferred, `provider-signed` must fail closed and the docs must state the limitation. | A forged attestation (valid self-digest, fabricated signature string) is rejected by both verifiers. A correctly signed fixture passes. | M |

## Workstream B - Document and governance truth

| ID | Issue | Evidence | Deliverable | Acceptance | Size |
| --- | --- | --- | --- | --- | --- |
| B1 | The backup-evidence doc schema contradicts its own verifier, so following the doc always fails. | `docs/saas/hamravesh-backup-onboarding.md:71-105` uses `backup.id` and omits `created_at`, `checksum_payload`, and `attestation`. `scripts/verify_recovery_evidence.py:104-123,158` requires all of them. | Reconcile the doc to the verifier (preferred) or the verifier to the doc. Add a doc-schema conformance test. | A test asserts the fenced JSON in the doc satisfies the verifier's field contract, so doc drift fails CI. | S |
| B2 | The roadmap misstates what remains. | `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md:54` claims the remaining blockers are operational verification, not repo-implementation gaps. That is false for Phase 2 (identity is unbuilt) and misleading for the Phase 1 frontend items. | Reword to separate externally-gated operational evidence from open repository implementation, and link this plan. | The roadmap names the open implementation workstreams and makes no implementation-completeness claim. | S |
| B3 | Documented behaviour diverges from the code. | `docs/bff-boundary-adr.md:40-41` claims origin controls and rate limiting; neither exists. `docs/security/rate-limit.json` reports `rate_limiting: passed` while its `observed` text describes session fail-closed behaviour. `spa-bff/README.md:29` states `BFF_REQUEST_TIMEOUT_MS` default `120000`; `spa-bff/src/config.ts:18` is `20_000`. `spa-web/README.md:53-56` and `docs/CONFIG_REFERENCE.md:116-117` document two env vars no code reads. `docs/bff-boundary-adr.md:232` says 7 test files and 65 tests; actual is 9 and 68. | Correct each claim to match observed behaviour, or implement the missing control under D4. Evidence JSON must describe what was actually observed. | No document claims a control that is not implemented. Evidence JSON accurately describes its control. The docs link check still passes. | S |
| B4 | The performance package sits inside a stale ledger. | `docs/architecture/ARCHITECTURE_BACKLOG.md:5` still reads `Status: ACTIVE - P0-00 performance recovery in progress`, while its P0-01 to P0-07 declare tenancy scope that `docs/ADR-001-multitenant-data-access-boundary.md` marks permanently rejected. Line 178 claims the performance probe is part of the production-readiness gate; no such probe exists. | Split the document: retain and re-scope a performance package, and mark the tenancy packages historical with a pointer to ADR-001 and the roadmap. Remove the false probe claim or satisfy it via C3. | The document no longer presents rejected tenancy scope as active work, and its remaining active package matches C1 to C3. | S |
| B5 | The RLS gate name implies rejected architecture. | `.github/workflows/ci.yml:79,133-134,470,480`; `scripts/check_rls_enabled.py:1-15`. The check itself is legitimate PostgREST exposure hardening. | Rename the CI job to a PostgREST/exposure name. Add a header comment to the script stating it is Supabase/PostgREST hardening unrelated to tenant isolation. Reference the distinction in `docs/architecture/ARCHITECTURE.md` and the lifecycle registry. | A reader cannot mistake the gate for tenant-isolation enforcement, and the check still runs and still gates CI. | S |
| B6 | The quality-gate baseline expires 2026-09-30 and will hard-fail every commit and CI run on 2026-10-01. | `scripts/check_quality_gate_baseline.py:46` fails when `expires_on < today`. `docs/QUALITY_GATE_BASELINE.md:16-17` sets QG-001 (repo-wide Ruff format) and QG-002 (repo-wide mypy) to 2026-09-30. The same script is a `always_run` pre-commit hook. | Either expand the gates to the promised scope or re-review and re-date the baseline items with a written rationale. | `python scripts/check_quality_gate_baseline.py` passes with dates that are not already expired, and the disposition is recorded. | S-M |
| B7 | Repository memory has gaps and an unmerged change set. | `docs/WORKLOG.md` is gitignored (`.gitignore:86`) and its newest entry is 2026-09-01, so it misses the OIDC and stateless-logout commits. The working tree holds uncommitted changes to `spa-bff/src/session.ts`, `src/saas/control_plane.py`, `src/saas/identity_contract.py`, four docs, and untracked `src/saas/entitlement_policy.py`, `identity_ports.py`, `operational_evidence.py` plus their tests. | Commit or explicitly park the work in progress. Append worklog entries for the OIDC and revocation work per the append-only discipline in `docs/ARCHITECTURE_DELIVERY_SYSTEM.md`. | `git status` is clean, or the parked work is documented with a resume condition. The worklog reflects the recent commits. | S |
| B8 | Declared surfaces are inert. | `spa-web/src/components/atlas-shell/AdminModePanel.tsx:17` declares a `security` tab absent from `ADMIN_TABS:19-26` with no render branch. `useAiProgressAssist.ts:76-164` never calls `aiProgressDecision()` (`shellAnalyticsUtils.ts:107-137`), so documented `NEXT_PUBLIC_OKR_AI_SYNC_*` env vars are inert. `RitualModePanel.tsx:4` imports `rtlStyle` and never uses it. | For each, implement or remove. Either disposition is acceptable; leaving a declared surface inert is not. | No unreachable declared UI tab, no documented-but-unread env var, no dead import. C4's linter will catch the last one. | S |

## Workstream C - Frontend performance corridor and quality gates

The performance items originate in the P0-00 package of
`docs/architecture/ARCHITECTURE_BACKLOG.md` (lines 145-181), which names
`Owner: frontend/...` and `Risk: Critical`.

| ID | Issue | Evidence | Deliverable | Acceptance | Size |
| --- | --- | --- | --- | --- | --- |
| C1 | No client caching for current user, cycle list, or team list. The shell refetches on every mount, and the cycle list is fetched twice per mount. | `useAuthBootstrap.ts:11-34` calls `/api/session/me` per mount. `useDeepLinkCycleBootstrap.ts:146-155` and `useCyclesSource.ts:35-44` both issue the identical `cycles.all` plus `cycles.active` pair, so a mount costs five read requests before the snapshot starts. `useAdminResources.ts:38-89` refetches users and teams on each admin entry. No React Query or SWR dependency exists. | Add a minimal short-TTL cache module in the existing hook style, with explicit invalidation wired to the mutation paths that change those three datasets. Route both cycle sources through one shared cache entry so the duplicate pair collapses to one. | Navigating between modes issues no duplicate session, cycle, or team fetch within the TTL, and the cycle pair is requested once per mount. A mutation that changes a cached dataset invalidates it. Tests cover TTL expiry, invalidation, and the in-flight dedupe. | M |
| C2 | No Suspense streaming. All ten Atlas panels are eagerly imported into one client component. | `AtlasShell.tsx:36-51` eager imports. No `loading.tsx`, `error.tsx`, or `not-found.tsx` under `spa-web/src/app`. No `React.lazy` or `next/dynamic` in `src`. | Add route-level `loading.tsx`, `error.tsx`, and `not-found.tsx`, and code-split the mode panels so the shell becomes usable before the snapshot resolves. | The authenticated shell renders usable chrome before the snapshot resolves. The `useShellAccessControl` login redirect, admin role gate, and forced-password-change flow are unchanged and still covered by tests. | L |
| C3 | The stated page-load budgets are asserted nowhere, and the backlog claims a probe that does not exist. | No `performance.mark`/`measure` or web-vitals usage in `spa-web/src`. The SPA never consumes the BFF `Server-Timing` header emitted at `spa-bff/src/server.ts:38-53`. No performance probe exists under `scripts/` or `tests/`. | Add a repeatable page-load budget probe wired into `justfile` and CI, failing on material regression. Evaluate the Playwright E2E setup and `spa-web/vitest.config.ts` and choose the cheapest option that is genuinely useful. | The probe runs in CI, fails when the budget is materially exceeded, and is referenced by the performance package's definition of done. | M |
| C4 | No lint gate for either JS/TS package, and `spa-bff` has no `typecheck` script. | No ESLint, Prettier, or Biome config exists anywhere. `spa-bff/package.json:10-19` has `build` but no `typecheck`. Root `package.json:9-13` covers only `spa-web` typecheck plus `spa-bff` build. | Add a minimal flat-config ESLint covering both packages with rules that matter here: unused variables, no explicit `any`, no floating promises. Add a `spa-bff` typecheck script. Wire both into root `package.json` and `justfile`. | `just lint` and `just typecheck` cover both JS packages. The dead import at `RitualModePanel.tsx:4` is surfaced as a violation. | M |
| C5 | In-app password change is unreachable. | `PasswordChangePanel.tsx` is mounted only from `spa-web/src/app/login/page.tsx:95`, and its `compact` prop is never passed as true. | Add an in-app entry point, with the admin/settings surface as the natural home, and cover it. | A signed-in user can change their password without signing out. Tests cover success and failure paths. | S-M |
| C6 | Frontend E2E coverage is thin. | `tests/test_e2e_playwright_spa_login_to_atlas.py:843-892` covers login, timer start and stop, check-in submit, weekly PDF job, admin cycle creation, and sign-out across three roles. It does not cover retrobox, timeline, dashboard, daily, alignment, admin users/teams/backup/audit, deep links, or RTL. | Extend E2E coverage to the listed routes. | Each listed route has at least one role-parameterised happy-path E2E. | M |
| C7 | The `spa-bff` local test setup collects duplicates. | `spa-bff/tsconfig.json` includes `test/**/*.ts`, so compiled tests land in `dist/test/*.test.js`, and `spa-bff` has no `vitest.config.ts`. Locally vitest collects `dist/` duplicates as well as `test/*.test.ts`. CI escapes only because `dist/` is gitignored. | Add `spa-bff/vitest.config.ts` excluding `dist/**`. | A local `npm test --workspace spa-bff` collects each of the 9 test files once, with no `dist/` duplicates. | S |
| C8 | Every navigation remounts the shell. Eight non-login routes each rendered `AtlasShell` as a near-identical wrapper, so client-side navigation repeated the entire bootstrap waterfall instead of reusing the mounted shell. | `spa-web/src/app/page.tsx:1-9` and the equivalents under `admin/`, `check-in/`, `daily/`, `dashboard/`, `retrobox/`, `timeline/`, and `weekly/` all rendered the same component. This is the mechanism behind the "across navigation" defect in `docs/architecture/ARCHITECTURE_BACKLOG.md:158`. | Adopt a shared Next.js route group layout that renders `AtlasShell` once and keeps it mounted across mode navigation, with the mode derived from the pathname. Consolidate the duplicated route files. | Navigating between modes does not remount the shell: the session bootstrap, cycle bootstrap, and snapshot effect each run once, and the snapshot poll is not restarted on navigation. | M |
| C9 | Forced password change is bypassable. | `readSessionUser()` returns `must_change_password` (`spa-web/src/lib/api/auth.ts:10`), but only `login/page.tsx:80-83` acts on it. `useAuthBootstrap.ts:15-19` calls `setUser` unconditionally and `AtlasShell` never inspects the flag, so navigating directly to `/` or reloading after login reaches the shell without the prompt. | Enforce the flag at the shell boundary, in the same place role gating is enforced, so it cannot be bypassed by navigation. | A user with `must_change_password: true` is forced to the change flow on any route; a cached or seeded session cannot bypass it. | S |

## Workstream D - Enterprise identity (Phase 2)

Hard prerequisite: D1 must land before any real login path is exposed. Shipping
an OIDC login without signature verification would be worse than having no login.

| ID | Issue | Evidence | Deliverable | Acceptance | Size |
| --- | --- | --- | --- | --- | --- |
| D1 | No ID-token signature verification exists anywhere. | `src/saas/identity_contract.py:223` only string-compares `jwks_uri` during discovery. There is no JWK fetch and no RS256 or ES256 verification. `src/saas/identity_ports.py:93-104` accepts a caller-supplied `signature_valid=True` as its only trust signal. | Implement JWKS fetch and signature verification in the BFF callback, before any claim is trusted. Select the key by `kid`, allow only RS256/ES256/PS256, and hard-reject `none` and every `HS*` algorithm (algorithm confusion). Verify `iss` exactly, `aud` contains the client id, `exp`/`iat` within a 60-second clock skew, and `nonce` in constant time. Cache the JWKS in-process with a TTL and refetch once on an unknown `kid`. | A token with a valid payload and invalid signature is rejected. `alg: none` and an `HS256` token signed with the JWKS public key are both rejected. A correctly signed fixture passes. | M-L |
| D2 | No OIDC login exists. The callback cannot live in the BFF alone. | `spa-bff/src/server.ts` exposes only `/session/login`, `/session/me`, `/session/logout`. The browser never reaches the BFF directly: `spa-web/src/lib/bff-proxy.ts:3` resolves `BFF_PUBLIC_ORIGIN`, and all browser session traffic goes browser to `spa-web` route handlers (`spa-web/src/app/api/session/{login,logout,me}/route.ts`) which relay `Set-Cookie`, so cookies are stored on the **spa-web origin**. `redirect_uri` must therefore be the public SPA origin plus a new Next passthrough, not a BFF path. | Build the flow across both packages: BFF `/session/oidc/authorize` and `/session/oidc/callback` with `state`, `nonce`, and PKCE S256, plus matching `spa-web/src/app/api/session/oidc/{authorize,callback}/route.ts` passthroughs. Reuse the existing session issuance, cookie, and CSRF helpers rather than re-implementing them. Fail closed on every missing trust signal with a distinct status and error code per failure mode. | A full authorization-code login against a mock IdP issues a working session on the spa-web origin. Replayed `state`, mismatched `nonce`, a tampered code, and unconfigured identity each fail closed with a distinct tested response. | L |
| D3 | Session revocation is process-local, fails open, and is unreachable in production for two independent reasons. | `spa-bff/src/session.ts:7` holds an in-process `Map`; `isSessionRegistryActive` returns true for a null, empty, or unknown session id (`:132-139`). `revokeSessionsForIdentity` is called only from `test/identity_session_revocation.test.ts`. More seriously, `external_subject` exists at exactly three lines, all in `session.ts` (`:19,71,180`), and `normalizeSessionUser` (`server.ts:169-179`) never copies it, so every real session records `externalSubject: undefined` and the identity match can never succeed. | Fix the dead field end-to-end (preserve `external_subject` in `normalizeSessionUser`, and have the backend return it, which cascades into the OpenAPI, route-policy, and allowlist regeneration chain). Introduce a revocation port with an explicit tri-state result (`active` / `revoked` / `unavailable`), where `unavailable` denies and maps to 503 rather than allowing. Expose a real deprovision route with admin plus CSRF enforcement, and a service-to-service variant for SCIM. | Revocation on one instance is observed by another. A genuine logout invalidates the server-side session. An unknown session id is rejected in production. An unreachable store denies rather than allows. | L |
| D4 | The BFF has no rate limiting and no origin enforcement, while the docs claim both — and the new OIDC routes are outside every existing gate. | No rate-limit or origin code in `spa-bff/src`; the only mention is a comment at `proxy.ts:100-102`. The CSRF rejection branch at `server.ts:550-558` has no test because every test supplies a valid token. `POST /session/login` has no session, CSRF, or origin check; `/session/logout` has no CSRF or session check. The BFF-native `/session/oidc/*` routes bypass both the allowlist and the backend service-token rate limiter (`backend_app/security.py:205-217`), so an attacker could drive unbounded JWKS fetches and token exchanges. | Add an `onRequest` rate limit with a general bucket and a tighter auth bucket covering `/session/login`, `/session/oidc/authorize`, `/session/oidc/callback`, and the proxied login, returning 429 with `Retry-After`. Add an origin check for cookie-authenticated state-changing routes, and add CSRF gating to login and logout. Ship this with D2, not after it. | Rate-limit and origin rejection are enforced and tested. An invalid-CSRF request receives 403 `INVALID_CSRF_TOKEN` in a test. A third request from one IP against a limit of two receives 429. | M |
| D5 | SAML, SCIM, MFA policy, and entitlements are unbuilt. | `src/saas/identity_ports.py` is ports plus in-memory test doubles with zero production importers. `src/saas/entitlement_policy.py` is inert: `enforcement_enabled` defaults false and `pre_saas()` hard-disables it. `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md:99-117` targets all of these in Phase 2. | Sequence behind D1 to D4 and behind a concrete customer requirement: SCIM provision and deprovision, SAML where required, MFA policy passthrough, and entitlement enforcement consistent across UI, API, and worker paths. | Each capability, when taken, has a contract test and a fail-closed default. Entitlements are enforced consistently across UI, API, and worker. | L each |
| D6 | Two mutually incompatible session-token formats already coexist, so neither side's token can be validated by the other. | `src/saas/identity_contract.py:457-501` `issue_app_session_token` emits `{v: "oidc-session-v1", actor, username, provider, subject, email, ...}` with no `sid` and no `user` object. `spa-bff/src/session.ts:221` requires `v === "v1"` and reads `payload.sid` plus `payload.user`. Python serializes with `json.dumps(sort_keys=True)`, TypeScript with insertion-ordered `JSON.stringify`, so the bytes never match either. | **DECIDED (D6-1, BFF owns the session).** The BFF remains the only minter. Mark the Python `issue_app_session_token` / `verify_app_session_token` pair (`identity_contract.py:457-501`, `:503`) as deprecated, non-authoritative, and scheduled for removal; it must never be treated as a second authority. The boundary between D6-1 (deprecate) and the follow-up D6-4 (delete outright) is a single open question: whether any consumer outside this repository verifies Python-issued tokens. Until that consumer search is run, deprecate rather than delete. Record the current Python mint formula (tag `oidc-session-v1`, the flat claim set, and `separators=(",",":")` with `sort_keys=True`) in this plan as the reference, so the search can recognise the real artefact later; recording only, no implementation. | Exactly one implementation can mint a session the BFF accepts, and the other is documented or removed. A test asserts the BFF rejects a Python-issued token. | S-M |
| D7 | `token_version` is frozen at login on the proxy path, so a mid-session revocation is not seen by ordinary API calls. | `spa-bff/src/server.ts:201-203` forwards `x-okr-token-version` only when the cookie carries it, and the cookie is minted from the login response at `:390-394`, so the value is fixed for the whole TTL. `/session/me` re-validates, but the `/api/backend/*` path forwards the stale value at `:587-590`. Separately `backend_app/security.py:261` resolves the actor scope without a `token_version`, so the forwarded-role-claim check can pass against a stale scope. | Decide whether a `token_version` bump must invalidate proxied requests within a bounded time; if so, re-resolve it on the proxy path or shorten the session TTL, and pass the version into the backend scope resolution. | Revoking a user's sessions takes effect on the next proxied request within a documented bound, and the bound is tested. | M |
| D8 | OIDC user resolution depends on an unverified identity assumption. | `SessionUser.id` is a required positive integer (`spa-bff/src/session.ts:10`, enforced at `session.ts:161` and `server.ts:160`) and an ID token cannot supply it. The only path that avoids a backend change is calling the existing `GET /v1/auth/me` with `x-okr-actor: <email>`, which relies on the internal `username` happening to equal the email (`backend_app/routers/platform_routes.py:128-142`). **Assumption REFUTED against real provisioning (read-only counts, 2026-09-20).** On the database named by `deploy/docker/.env` the `public."user"` table has exactly 1 row: `username LIKE '%@%'` = 0, non-email usernames = 1, and the row is `username = 'admin'` — the hardcoded bootstrap admin (`src/crud_auth_helpers.py:1082-1089`). Normalized-username collisions = 0, non-lowercase or padded usernames = 0. The table's 12 columns are `id, username, password_hash, must_change_password, password_changed_at, display_name, role, manager_id, created_at, is_active, team_id, token_version`: there is **no `email` column and no `external_subject` column**, so `username` is the only identity string that exists. | **Outcome locked to the M-L path.** The cheap `/v1/auth/me` exchange cannot resolve any user in the current database, because the sole account's username is not an email, and nothing in the repo provisions an email-username row (no JIT/OIDC provisioning path exists). Do not implement D2's user resolution on the cheap path. Either add an `external_subject` column on `User` (a migration, so it is separately gated by the `alembic/versions/` freeze and by whatever backfills the bootstrap admin) or add a backend enterprise-exchange endpoint taking verified `{iss, sub, email}`, which cascades into the full OpenAPI, route-policy, and auth-matrix regeneration chain. Re-run the counts before implementing, and confirm the invariant on the target deployment, not only this one. | The chosen resolution path is verified against real provisioning, or the new endpoint exists with its contract, allowlist entry, and matrix row. | S to verify, M-L if the endpoint is needed |
| D9 | An unverified `email_verified` claim is accepted as identity, so an unverified or self-asserted address can claim another user's account. | `email_verified` is carried but never enforced. It appears at `src/saas/identity_contract.py:436` (read from the ID token, defaulting to `False` when absent) and `:487` (copied into the session payload), plus four assertions in `tests/test_saas_identity_contract.py`. A repository-wide search of `*.py` / `*.ts` / `*.tsx` finds no comparison of the claim against `true` and no rejection path. The identity contract maps the email straight into both `actor` and `username` (`:482-483`), and the backend resolves the actor by exact `User.username` match (`backend_app/routers/platform_routes.py:138-142`), so an unverified email is sufficient to assume that identity. | Fail the OIDC exchange and the session-minting path closed when the claim is missing, not a boolean, or `false` — treat `email_verified` as required, not advisory. Whether enforcement is possible depends on the outstanding human answer about whether this IdP always asserts the claim as true for legitimate users; if it does not, define an explicit fallback that does not silently trust the address. Add a distinct error code per failure mode, consistent with D2's fail-closed convention. | A token whose `email_verified` is missing, `false`, or non-boolean fails closed at the exchange and mints no session, with a test for each case. A token with `email_verified: true` still succeeds. | S to verify, M to implement |

### D6 reference: the current Python mint formula (recorded, not implemented)

Recorded so the later consumer search for D6-4 can recognise the real artefact
instead of guessing. This is a description of what exists today, not a proposal
and not code to add.

- Tag: `"oidc-session-v1"`, emitted as the `v` field.
- Shape: a single flat object, no nested `user` object and no `sid`.
- Fields: `v`, `iat`, `exp`, `expires_at`, `actor`, `username`, `provider`,
  `subject`, `email`, `email_verified`, `name`, `issuer`, `aud`, `role`, `roles`.
- Serialization: `json.dumps(payload, separators=(",", ":"), sort_keys=True)`,
  then base64url.
- Encoding: `f"{payload_part}.{signature}"` where `signature` is the lowercase
  hex HMAC-SHA256 of the base64url payload, keyed by the configured secret.
- Divergence from the BFF format, for the search's benefit: the BFF writes
  `v: "v1"` and requires `sid` plus a nested `user` object, and serializes with
  insertion-ordered `JSON.stringify`, so neither the tag, the shape, nor the
  bytes match.

A consumer search should look for the literal `oidc-session-v1`, for a
`payload.signature` split on a single `.`, and for verification callers of
`verify_app_session_token`.

## Workstream E - Provider-gated and externally blocked

Recorded so these are not mistaken for startable work. Do not begin one without
its trigger.

| ID | Item | Classification | Trigger, and what code could do meanwhile |
| --- | --- | --- | --- |
| E1 | Provider-backed backup and restore | EXTERNAL | Requires a selected provider and its API contract. `select_backup_provider(test_only=False)` raises, `LocalBackupProvider` is explicitly test-only, and `deploy/darkube/prerelease/README.md:24` forbids inventing a Darkube API. Writable now: a provider-agnostic HTTP backup provider skeleton and config loader behind the existing ports. |
| E2 | Runtime adapter for a real deploy | EXTERNAL | `RuntimeAdapter` is a Protocol whose only implementation is `LocalRuntimeAdapter`, which never starts a service. Writable now: define the adapter shape, or document that the local adapter is the only one. |
| E3 | Paired application rollback rehearsal | EXTERNAL plus CODE | `darkube-prerelease.yml` takes `rollback_result` as a manual choice input and `verify_darkube_deployment.py` verifies one release only. Writable now: emit the `execution` block that `verify_rollback_record()` already requires at `scripts/verify_rollback_evidence.py:197-204`, so the strict validated path becomes reachable. |
| E4 | Kubernetes manifests for the SPA and BFF | CODE, low priority | `deploy/k8s/*.yaml` are placeholders (`REPLACE_WITH_RELEASE_DIGEST`, empty secret strings) with no web or BFF Deployment, no Ingress, ConfigMap, HPA, or namespace, and no workflow references them. |
| E5 | Named operations owner and explicit real-data approval | EXTERNAL, human | `UNASSIGNED` in the roadmap, `docs/saas/phase-1-entry-evidence.md:64`, and `docs/saas/release-signoff.md:10`; `real_data_approval` is false. No engineering action closes these; the verifiers already reject `UNASSIGNED`. |
| E6 | Phase 3 scope | DEFERRED | Per-environment SLOs and alert routing, tenant-aware audit tooling, rolling-version compatibility and expand/contract migrations, disaster-recovery drills, noisy-neighbor protection, data residency, and a cost and capacity model. |

## Sequencing

The five suggestions from the repository review map onto these phases:
suggestion 1 (the defects) and suggestion 2 (document reconciliation) are Phase 1,
suggestion 3 (identity) is Phase 3, suggestion 4 (frontend plus lint) is Phase 2,
and suggestion 5 (leave provider work to operations) is Phase 4.

### Phase 1 - Integrity and truth

Items: A1, A2, A3, A5, B1, B3, B5, B6, B7, B8, C7, C9.

No external dependency. Rationale: A1 and A2 are outright defects. A3 closes the
gap between a mandatory gate and its enforcement. A5 closes an evidence-forgery
hole. B6 is a dated hard failure on 2026-09-30. B3, B5, and B8 remove the
divergences that would otherwise mislead Phase 2 and Phase 3. C9 is a small
security-relevant gap that must not be tangled into the performance refactor, so
it belongs here rather than in Phase 2.

Progress:

| Item | Status | What landed |
| --- | --- | --- |
| A1 | Done | Bootstrap guard restored in `scripts/deploy_saas_release.py`; `tests/test_cli_entrypoint_bootstrap.py` guards all five operator CLIs. |
| A2 | Done | `register-target` subcommand added; shared `validate_restore_target()` closes the registration-time safety gap; backup to register to restore journey covered end to end. |
| C9 | Done | Forced password change enforced at the shell boundary (`useShellAccessControl.ts`) and the bypassing redirect removed from `login/page.tsx`; helper and boundary tests added. |
| A3, A5, B1, B3, B5, B6, B7, B8, C7 | Not started | Phase 1 remainder. |

### Phase 2 - Frontend performance corridor

Items, in order: C1 and C4, then C2, C3, and C8, then C5 and C6.

C1 and C4 land first because they are cheap and de-risk the larger refactor. The
C4 linter should exist before C2 and C8 rewrite large files. C8 (one mounted
shell) and C1 (cached bootstrap) address the same defect from two directions, so
they must land as separate commits: C1 removes the duplicate fetch, C8 removes
the remount that repeats it. Land C1 first, because C8 without C1 still refetches
on every navigation.

Implementation notes for this phase:

- Recommended cache TTLs are 30 seconds for the session and 60 seconds for cycles
  and admin resources, with namespace invalidation (`session`, `cycles:<user>`,
  `admin:<user>`). The session TTL must stay below the 45-second snapshot poll.
  **Superseded in part, see the progress table below:** the session is not cached
  at all, and invalidation is coarse rather than per-namespace. Targeted mutations
  read with `bypassCache: true` and write the fresh result back, which re-seeds the
  entry instead of only emptying it, and the only whole-cache callers are sign-out
  and a database restore. The 60-second TTL for cycles and admin resources was
  adopted as recommended.
- Prefer a hand-rolled cache module over React Query or SWR. There are only three
  resources, each already has an explicit refresh path, and a new runtime
  dependency must clear `scripts/check_dependency_manifest.py` and the
  dependency-scan and licence gates.
- For C3, the PR-gating check should be a deterministic request-waterfall test
  (assert parallelism, de-duplication, and zero refetch on a warm cache) rather
  than a wall-clock assertion, which flakes in CI. The live `Server-Timing`
  budget probe belongs to release evidence. `spa-bff/src/server.ts:38-53` already
  emits the header, `spa-web/src/lib/bff-proxy.ts:8-18` already forwards it, and
  `scripts/slo_probe.py:36-50` already parses it, so the plumbing exists.
- Stage C4: land the config with the noisy rules at `warn`, fix the one known
  dead import, then ratchet. Error-level `exhaustive-deps` and
  `no-floating-promises` on the first run will fail CI on pre-existing debt.
  **Superseded in part by measurement; see the C4 lint rows below.**
  `exhaustive-deps` (18 findings) did need `warn`, but `no-floating-promises`
  had a single instance and `no-explicit-any` had none at all, so both those
  rules landed as `error` once their one-off sites were fixed.

Progress:

| Item | Status | What landed |
| --- | --- | --- |
| C1 | Implemented (cycles and admin); session deliberately excluded | A short-TTL read-through cache in `spa-web/src/lib/resourceCache.ts` with in-flight de-duplication and no caching of failures. `cycles.all` + `cycles.active` now come from one shared entry, so the deep-link bootstrap, the top-bar cycle source, and the admin panel issue one pair between them instead of one each. The admin `users.all` + `teams.all` pair is cached the same way, and sign-out clears the whole cache. Mutation paths pass `bypassCache` and re-seed the entry. Two corrections against what this phase recommended below: invalidation is coarse rather than per-namespace, and the session is not cached. |
| C1 restore fix | Fixed | A whole-database restore replaced the database but reloaded through the cache, so the admin panel showed pre-restore data for a full TTL. `handleAdminBackupRestore` now clears the whole cache before reloading, and refreshes the top-bar cycle list, which is a separate owner of cycle state and was not covered by the admin reload. A test asserts the clear happens *before* the reload. |
| C1 note | Session not cached, by decision | `readSessionUser()` carries `role`, and the gate in `useShellAccessControl.ts` decides what chrome renders. Caching it would widen the window in which a server-side demotion still shows admin controls from one round trip to the whole TTL, which this plan flags as the highest-blast-radius risk in the workstream. Because C8 removed the per-navigation remount, the session is now read once per shell lifetime, so there is nothing left to gain. |
| C8 | Implemented, open in PR #177 with CI green; drill open | Lands ahead of the order stated above: C8 removes the remount, so the per-navigation cost C1 targeted is already gone and C1's remaining gain is the duplicate pair on a single mount. `VERIFIED` still requires the warmed-stack navigation drill recorded in the status ledger. |
| C4 typecheck half | Landed | `spa-bff` now has a `typecheck` script (`tsc --noEmit -p tsconfig.json`), root `typecheck` calls it instead of the emitting `build`, and a `SPA BFF typecheck` step in `spa-quality` exercises the script so it cannot rot. `just typecheck` therefore covers both JS packages, which is half of this item's acceptance criterion. |
| C4 lint half | Landed | `eslint.config.mjs` is a flat config, root `npm run lint` and `just lint` run it, and a `JavaScript lint gate` step early in `spa-quality` keeps it honest. The script passes both whole packages and the config's `ignores` decide what is skipped, so the scope is every hand-written file: 145 files, 0 errors, 37 warnings. Generated output is the only thing excluded. An earlier revision listed paths by hand and silently missed six files, including a `vitest.config.ts`; that list is gone rather than extended, because a hand-maintained list is what failed. `no-explicit-any` and `no-floating-promises` are `error`; `no-unused-vars` and `exhaustive-deps` are `warn`, and the triage of those 37 is a separate open item below rather than being counted as cleared. |
| C4 dependency realignment | Landed | Forced by `npm audit fix --force` moving `spa-bff` from vitest 3.x to 5.0.1, which the user chose to keep. Two defects came with it and both are fixed. First, `spa-bff/package-lock.json` still declared `^3.2.4` while the manifest said `^5.0.1`, so `verify_dependency_licenses.py` was auditing a tree that no longer matched its manifest; regenerated, and the gate passes on the new tree. Second and more serious, vitest's default test `exclude` shrank in the 4.x line to only `**/node_modules/**` and `**/.git/**` (see the v4 migration guide, "Simplified exclude"), so `dist` is no longer excluded by default. Because `spa-bff/tsconfig.json` compiled `test/**/*.ts` into `dist/test/`, any tree with a build present collected every test twice and the duplicated servers pushed the slowest test past its 5s budget; CI escaped only because `SPA BFF tests` runs before `SPA BFF build`. Fixed at the root rather than at the symptom: `tsconfig.build.json` now emits only `src`, so tests cannot enter `dist` at all, the Dockerfile copies the new config (without which the image build would fail), the CI build-cache key hashes it, and `vitest.config.ts` restores the documented pre-4.x exclude list. Verified in the other direction too: spa-bff's tests use none of the documented v4/v5 breaking APIs — no `spyOn`, snapshots, constructor mocks, `vi.mock`, or `vi.hoisted` — and the three `toHaveBeenCalledTimes(1)` assertions use per-test local mocks, so the new `clearMocks: true` default cannot affect them. |
| C4 build emit correctness | Landed | A second, more serious defect surfaced while checking that the build change was safe, and it is pre-existing rather than introduced here. `tsc --incremental` trusts its `.tsbuildinfo` and never verifies that the output files still exist, so when a build-info is present and `dist` is absent, `tsc` exits 0 having emitted nothing. Isolated with four runs: stale build-info with `dist` deleted exits 0 with no output, deleting both produces output, a fresh build-info with `dist` deleted again exits 0 with no output, and the original `tsconfig.json` build behaves identically — so the original build was affected too. This matters because the `spa-build-cache` step restores `spa-bff/.cache` (which holds the build-info) but not `spa-bff/dist`, so on a cache hit whose build-info matches the current sources, `SPA BFF build` reported success while producing no artifact, and nothing in `spa-quality` checked that the artifact existed — a gate that verified nothing. The container is unaffected, and that was checked rather than assumed: `spa-bff/Dockerfile` copies only `package*.json`, both tsconfig files and `src`, never `.cache`, so the image build always starts cold, and CI's Container Image Build Gate builds that file from a fresh context. Fixed at the root by making the emitting build non-incremental in `tsconfig.build.json`, since `tsc` then always emits, and verified adversarially — with a deliberately planted stale build-info and `dist` deleted, the build now produces `dist/src/server.js`, the exact case that previously produced nothing. `typecheck` keeps incremental, which is sound because `--noEmit` has no outputs to lose. |
| C4 open question | Not started | `spa-bff/package.json` declares `engines.node: ">=20"`, but vitest 5.0 requires Node `>=22.12.0`. CI runs `node-version: "22"` and the image is pinned to `node:22-alpine`, so nothing fails today and the repository sets no `engine-strict`, meaning npm only warns. It is still an inaccurate declaration for anyone developing on Node 20. Left unresolved on purpose: tightening a runtime contract without being able to inspect the pinned image locally would be a guess, and the image's Node version could not be read because the local Docker daemon is unreachable. |
| F1 - Retry timeout option does nothing | Not started, highest priority of the F items | Confirmed defect, found while auditing the lint warnings. `spa-web/src/lib/api/http.ts` declares `perAttemptTimeoutMs?: number` on the exported `RetryWithFetchOptions` and destructures it with a default of `8_000`, but the identifier is never read again: it appears only at its declaration (line 173) and its destructuring (line 185), and `retryWithFetch`'s two call sites in `api/atlas.ts` never pass it. So no attempt is ever time-boxed and a hung request can occupy a retry slot indefinitely, while the option advertises a guarantee it does not provide. No caller passes it today, so nothing misbehaves yet; the false contract is the defect. The honest fix is to thread an `AbortSignal` into `fetchFn` and abort at the deadline, with a test that a never-settling fetch is aborted, which is a behaviour change to a shared helper and so belongs in its own change rather than an audit-cleanup commit. |
| F2 - BFF proxy discards its error | Not started | `spa-web/src/lib/bff-proxy.ts` catches a failed upstream request and returns a generic 502 with the caught error bound but never used, and the module imports no logger. A failing BFF proxy is therefore undiagnosable from the application side. Recorded accurately: `spa-web/src/lib` contains no logging calls at all, so this is not a deviation from an existing convention in that layer but the absence of one, and fixing it means choosing a logging approach rather than adding a call. |
| F3 - Triage of the 37 lint warnings | Not started | The lint gate is green with 37 warnings, and they are tracked work rather than cleared findings. Triage done so far: the ones that looked most like missing authorisation checks are not — `AtlasShell.tsx:1160 canCreateForContext`, `AtlasShell.tsx:433 adminBackupFile` and `useAdminActions.ts:121 canMutateCycle` are values that are destructured or computed and then never read, so they are dead bindings whose permissions are enforced elsewhere; that claim was checked at the source and is deliberately not being reported as a security defect. Seven findings are of the `assigned a value but never used` shape, which is the shape F1 turned out to be, so each needs the same treatment rather than being assumed to be style. Eighteen are `exhaustive-deps`, of which `useShellAccessControl.ts:85` (a missing `isManager` dependency in the hook that gates admin chrome) is the one with the largest blast radius and should be examined first. |
| C4 lint evidence | Landed, gate green | The final config runs over `spa-web/src` and `spa-bff/src`, 131 files, with **0 errors and 37 warnings**. The toolchain is eslint 10.11.0, `@eslint/js` 10.0.1, `typescript-eslint` 8.70.0, `eslint-plugin-react-hooks` 7.1.1; ESLint 9 was measured first but is now EOL, so 10.x is what shipped. **`no-explicit-any` had zero violations**, so it could be `error` at no cost, which corrects the staging this phase recommended. All five error-level sites were fixed rather than downgraded: `no-floating-promises` 1 (`useSnapshotLifecycle.test.ts:135`, resolved with an explicit `void` plus a comment saying why the call is deliberately not awaited), `no-useless-escape` 2 (`shellDateUtils.ts:17`, `api/http.ts:134`), `no-require-imports` 1 (`spa-bff/src/config.ts:172`, resolved by the static `node:crypto` import its sibling modules already use), and `preserve-caught-error` 1 (`api/http.ts:200`, a rule new in ESLint 10, resolved by attaching `cause`). Two of those were proven behaviour-preserving before landing rather than assumed: the `[+\-]`→`[+-]` edits were checked against 22 inputs, 6 of them exercising the numeric-offset branch, with zero mismatches, and `cause` was confirmed non-enumerable, so no assertion or serialisation can observe it. |
| C2, C3, C5, C6 | Not started | Phase 2 remainder. |

### Phase 3 - Enterprise identity

Items, in order: D1, D3, D4, D6, D8, and D9 (the verification and decision steps),
then D2, then D5 and D7.

D1 is a hard gate: exposing any real OIDC login before signature verification
exists would be worse than having no login. D4 must ship **with** D2 rather than
after it, because the new unauthenticated OIDC routes bypass both the allowlist
and the backend's service-token rate limiter. D6, D8, and D9 must be resolved
before D2 is written, since they determine the session authority, the user
resolution path, and whether an unverified address may be trusted at all.

Progress:

| Item | State | Note |
| --- | --- | --- |
| D6 | Decided | D6-1 accepted: the BFF owns the session; the Python issue/verify pair is deprecated and non-authoritative. D6-4 (delete outright) is gated on a consumer search for the recorded mint formula. |
| D8 | Verified, assumption refuted | Read-only counts against the configured database found one non-email `admin` row and no `email` or `external_subject` column, so the cheap `/v1/auth/me` path cannot resolve any current user. Outcome locked to the M-L path. |
| D9 | Registered | New: `email_verified` is carried but never enforced. Acceptance criterion written; enforcement depends on an outstanding human answer about the IdP's claim behaviour. |
| D1, D2, D3, D4, D5, D7 | Not started | Phase 3 remainder. |

Implementation notes for this phase:

- The BFF session contract that D2 must reuse is not a JWT.
  `issueSessionToken` (`spa-bff/src/session.ts:48`) produces
  `<base64url(payload)>.<hex-hmac-sha256>` and `verifySessionToken:184-207` splits
  on the **first** dot and requires the signature to match `/^[a-f0-9]{64}$/`.
  The payload is `{ v, iat, exp, sid, user }` (`:22-28`) with `v === "v1"`.
  Adding a JWT library for ID-token verification therefore cannot collide with
  this format, but do not "unify" the two.
- Cookie attributes. Both cookies use `Path=/` with no `Domain`; they diverge only
  on `HttpOnly` and `SameSite`. The session cookie is `HttpOnly` + `SameSite=Lax`
  (`:285-301`); the CSRF cookie is deliberately not `HttpOnly` and is
  `SameSite=Strict` (`:324-340`) because double-submit requires JavaScript to read
  it. **An earlier draft of this plan claimed a path or domain divergence between
  them; that was wrong.** The real trap is that the OIDC callback is a cross-site
  top-level GET from the IdP, so a `SameSite=Strict` transaction cookie would be
  withheld and every login would fail with `OIDC_STATE_MISSING`. The transaction
  cookie must be `SameSite=Lax` and `HttpOnly`.
- Cookie paths are matched against the **public** path on the spa-web origin, not
  the BFF's internal path, because cookies are stored on the spa-web origin. A
  transaction cookie scoped to `/session/oidc` would never be sent; use `Path=/`
  with a short TTL, or scope it to the public `/api/session/oidc`.
- D1 library choice. `spa-bff` declares only `fastify`, and `jose`,
  `jsonwebtoken`, `openid-client`, and `jwt-decode` are absent from both
  `spa-bff/package.json` and the root `package-lock.json`. The BFF image runs
  `npm ci` from the root lockfile, so adding one requires committing **both**
  files. `jose` passes `scripts/check_spa_bff_boundaries.py`, which forbids only
  database/ORM clients and cross-package imports. As a zero-dependency fallback,
  `node:crypto` can import a JWK via `createPublicKey({ key, format: "jwk" })` and
  verify RS256 with `crypto.verify("RSA-SHA256", ...)` and ES256 with
  `dsaEncoding: "ieee-p1363"`; prefer the audited library and treat hand-rolled
  verification as a fallback only.
- D3 durability is constrained by a CI gate, not just by preference.
  `scripts/check_spa_bff_boundaries.py:24-45` fails the build on `redis`, `pg`,
  `postgres`, `ioredis`, and `@supabase/supabase-js`, so a durable revocation
  store cannot be a direct database or cache client. It must be an HTTP adapter
  over the signed service hop to a new backend endpoint. A simpler alternative
  worth considering first: drop the BFF revocation list and rely on the backend
  `token_version` check that already works (`spa-bff/src/server.ts:587-590`,
  tested in `spa-bff/test/token_version.test.ts`), accepting the D7 bound.
- Making `revokeSessionsForIdentity` async changes its callers.
  `spa-bff/test/identity_session_revocation.test.ts` calls it synchronously at
  lines 20 and 32 and will need `await`. `readSessionUserFromRequest`
  (`server.ts:182-190`) also becomes async, which affects its two call sites at
  `server.ts:436` and `:527`.
- Authentication in the BFF is inlined per route, not a hook or decorator. There
  are exactly three sites: `/session/me` (`server.ts:436`), the proxied
  `/api/backend/*` path (`:527`), and `/session/logout` (`:492`, which performs no
  authentication at all). A new auth decorator would be a structural improvement
  but is not required by any item here.
- D2 scope spans both packages. It includes new Next passthrough route handlers
  under `spa-web/src/app/api/session/oidc/`, mirroring the existing three.
- D4 must ship with D2, not after it, because the new unauthenticated OIDC routes
  bypass both the allowlist and the backend service-token rate limiter
  (`backend_app/security.py:205-217`), leaving JWKS fetches and token exchanges
  unbounded. The rate limiter should be an `onRequest` hook placed after the
  existing request-id hook (`spa-bff/src/server.ts:256-263`), keyed on
  `request.ip` (valid because `trustProxy` is enabled) with a general bucket and a
  tighter auth bucket. It is per-replica: with more than one BFF replica the
  effective limit multiplies, and this must be documented rather than implied.
- Allowlist mechanics are narrower than they first appear.
  `spa-bff/src/allowlist.ts` is generated from the hand-maintained
  `spa-bff/src/route-policy.json`, which the generator validates against the
  committed OpenAPI artifact and never rewrites, so its `pathPattern` fields are
  stale metadata. BFF-native `/session/*` routes need no allowlist change at all;
  only proxied `/api/backend/*` routes do. Adding a backend route requires the
  full sequence: `uv run python scripts/export_openapi.py`, `npm --prefix spa-web
  run gen:api`, `npm --prefix spa-bff run gen:api`, hand-edit `route-policy.json`,
  `uv run python scripts/generate_bff_allowlist.py`, then the `--check` drift gate.
  A new backend **mutation** route must also be added to
  `tests/test_backend_mutation_auth_matrix.py`'s route set or that test fails.
- Logging. `scripts/verify_logging_contract.py` inspects only
  `spa-bff/src/server.ts`, so a new `spa-bff/src/oidc.ts` is not covered by the
  gate. Never log `code`, `id_token`, `access_token`, `code_verifier`, `state`,
  `nonce`, or `client_secret`; enforce that in review.
- Open questions to resolve before implementation, none answerable from the repo:
  whether the IdP is a confidential client, whether `email` and `email_verified`
  are always present, and whether internal usernames equal email addresses.
  There is no OIDC configuration artifact and no `BFF_OIDC_*` or `OKR_IDENTITY_*`
  entry in any `.env.example`. **Status 2026-09-20:** the username-equals-email
  question is answered — no, refuted by read-only counts (see D8) — and is no
  longer open. The client-type and `email_verified` questions remain open and now
  bind D2 and D9 respectively.

### Phase 4 - Provider and external

Items: A4, E1, E2, E3, each only on its trigger. E4 opportunistically. E5 and E6
remain outside engineering scope.

Start the A4 design decision early even though its implementation lands in
Phase 4, because it needs a decision before it needs code.

## Verification drills

`docs/ARCHITECTURE_DELIVERY_SYSTEM.md` requires an item's purpose to be confirmed
against the running system before it can reach CLOSED. Green tests are not
sufficient. These are the drills for this plan.

| Workstream | Drill | Passes when |
| --- | --- | --- |
| A, release and recovery | On a scratch state file, run provision, then backup with `--test-only`, then register an isolated target, then restore, and confirm the checksums match. Then attempt a restore into an unregistered target and into a `live` target. | Both invalid restores fail closed, and the valid round trip succeeds end to end. |
| A5, attestation | Build an evidence file with a correct self-digest and a fabricated signature string. | Both verifiers reject it. A correctly signed fixture passes. |
| B, document truth | Run `python scripts/check_docs_hq_links.py`, `python scripts/check_quality_gate_baseline.py`, and the new doc-schema conformance test. | All pass, and every claim corrected under B3 matches observed behaviour. |
| C, frontend | Measure the authenticated page on a warmed stack and confirm the shell data budget. Navigate between modes and count session, cycle, and team fetches. | The shell budget is met and no duplicate fetch occurs within the TTL. |
| D, identity | Drive a full login against a mock IdP, then attempt a replayed `state`, a mismatched `nonce`, a tampered token, and an unsigned token. Then revoke on one instance and check the second. | Every attack fails closed, and revocation propagates across instances. |

## Status tracking

Register each item as a row in `docs/architecture-status.md` using the existing
five-column format and the `PLANNED -> IN-PROGRESS -> IMPLEMENTED -> VERIFIED ->
CLOSED` lifecycle. `IMPLEMENTED` means merged with CI green. `VERIFIED` requires
the matching drill above. Do not create a second active ledger; this register
feeds the existing one.

Append one entry per working session to `docs/WORKLOG.md`, always with a `Next:`
line and an explicit `Blockers:` line, per
`docs/ARCHITECTURE_DELIVERY_SYSTEM.md`.

## Edge cases and failure modes

- A2: registration must not weaken `UnsafeRestoreTarget`, and a live target must remain impossible to restore into.
- A5: cover forged attestation, algorithm confusion, an unconfigured or missing secret, and a future-dated `issued_at`.
- A4: whichever model is chosen, no route may expose an environment the operator never recorded.
- B5: rename the CI job without dropping the required-check wiring in `ci-result` (`.github/workflows/ci.yml:468-492`), or CI will silently stop enforcing it.
- C1: the cache must not serve a stale role after a role change or a token-version bump, and forced password change must still redirect. This is the highest-blast-radius risk in the plan: the role gate at `useShellAccessControl.ts:69-75` runs in an effect, after paint, so today a server-side demotion is corrected within one round trip. Prefilling the user from cache widens that window to the whole cache TTL, during which the demoted user still sees the admin sidebar entry and admin-only controls. Choose an explicit policy (render provisional-role chrome conservatively until the first fresh read resolves, or exclude the role from the cached object) and encode it in the cache test. Sign-out must clear the entire cache so one user's cycles and teams cannot leak to the next on a shared browser.
- C1: `sessionCycles` and `adminTeams` are React state, not just cache entries. Invalidation that touches only the cache leaves those states serving pre-mutation values, so the cache needs a subscription channel or the hooks need to read through it.
- C8: changing how often the shell mounts changes the lifetime of the 45-second and 600-second snapshot polls (`useSnapshotLifecycle.ts:16-22`) and the 30-second dashboard poll (`useAtlasModeData.ts:58,333`). Any change that makes the bootstrap effect's dependencies unstable restarts those intervals and can defeat the existing stale-request guard.
- C2: the login redirect, the admin gate, and deep-link bootstrap must survive the split, and a Suspense fallback must not flash authenticated chrome to an unauthenticated user.
- C3: a budget probe that is flaky or environment-dependent is worse than none; pin the measurement conditions and record them.
- D1: reject `alg: none`, pin the allowed algorithms, and never trust a client-supplied `signature_valid`.
- D2: `state` must be single-use and bound to the initiating browser. The PKCE verifier must not be recoverable from a stolen cookie alone. The callback must not be usable as an open redirect.
- D3: failing closed on an unknown session id must not lock out existing sessions at deploy time. Provide a documented migration or compatibility window.
- Documents: every new Markdown file needs the `Documentation HQ` backlink, LF line endings, no trailing whitespace, and a final newline, or the pre-commit hooks and `check_docs_hq_links.py` fail.
- B6: any documentation edit touching the two baseline items before 2026-09-30 must keep `check_quality_gate_baseline.py` passing.

## Acceptance criteria

1. `python scripts/check_docs_hq_links.py` passes, including the new README Documentation HQ links.
2. `python scripts/check_quality_gate_baseline.py` passes with dates that are not already expired.
3. Every Phase 1 item has a merged change and a status-ledger row.
4. No document claims a control, gate, or probe that does not exist.
5. `just lint`, `just typecheck`, `just test`, and `just contracts` cover both JS packages, and the corrected CI evidence jobs run.
6. Workstream E items are recorded as blocked with named trigger conditions.

## Assumptions

- The four most recent commits, covering the OIDC flow and stateless session logout revocation, are the intended baseline. The uncommitted working-tree changes are work in progress to be committed or parked under B7, not reverted.
- A vetted JWT library may be added to `spa-bff` with a `package-lock.json` update. Hand-rolled RSA verification is not acceptable.
- The single-tenant isolation decision in ADR-001 stands. No item reintroduces tenant identifiers or shared-database RLS.
- Provider selection, the operations-owner appointment, and real-data approval remain outside engineering control and are not scheduled here.
- `docs/WORKLOG.md` stays gitignored and local, per `.gitignore:86` and the lifetime table in `docs/ARCHITECTURE_DELIVERY_SYSTEM.md`.
- Persian mirrors of the new documents are not included in this plan. If the mirror convention in `docs/DOCUMENTATION_LIFECYCLE.md` must be satisfied immediately, treat it as an additional item.

## Out of scope

Shared-database multi-tenancy and RLS-based tenancy, per ADR-001. Restarting
`docs/architecture/PRE_SAAS_ARCHITECTURE_BACKLOG.md`. Microservice extraction.
Turborepo or Nx adoption. Data residency and regional deployment. Billing and
self-service provisioning. Removing the BFF without a new ADR and security-parity
evidence. Broad rewrites of `src/` or `backend_app/` for naming consistency.
Kubernetes work beyond E4.
