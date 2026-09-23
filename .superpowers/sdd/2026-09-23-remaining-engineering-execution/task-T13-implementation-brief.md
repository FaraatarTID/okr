Documentation HQ: [README](../../../README.md)

# T13 Frontend Performance Budget — Implementation Brief

Date: 2026-09-23  
Status: coordinator-approved local implementation scope. T15 full module and independent review now PASS. The warmed-stack numeric decision remains owner-gated.

## Canonical acceptance

C3 in `docs/REMAINING_ENGINEERING_PLAN.md` is authoritative and was reconciled against T13 in the execution plan and independently reviewed (`task-T13-canonical-acceptance-review.md`, PASS):

1. **PR CI:** deterministic browser request-waterfall regressions only—request ordering, parallelism of independent reads, de-duplication of shared reads, and no refetch while the shell/resource cache is warm. Do not assert elapsed-time thresholds in PR CI.
2. **Release evidence:** run an authenticated browser budget probe on a pinned, warmed stack. Pin/record browser, build/commit, stack readiness, data-access mode, and browser/resource-cache condition; collect browser timing and correlate forwarded `Server-Timing` values (`bff-upstream`, `app`, `data`). The report is evidence, not a provider-independent claim.
3. C3 remains open until an approved successful warmed-stack artifact is attached. Local fixtures and CI can prove request contracts, not live release performance.
4. Keep T13 separate from backend read-path/PgBouncer budgets T32/T35 and from T11's C8 shell/polling/role-freshness drill.

The current plan does **not** give a numeric page-load/LCP target or a precise aggregation formula for “page budget.” `docs/OBSERVABILITY_AND_RUNBOOKS.md` has backend/login/read SLOs, not an authenticated SPA page target. Do not borrow its API threshold or invent a frontend pass threshold. Until owner approval, the probe must report measurements with `score_status: "unscored"`; it may fail for authentication, route, missing measurement, or malformed output, but never because an unapproved timing number exceeded a threshold. Before marking a measured budget `pass`, the release owner must approve the metric, budget, sample count/aggregation, and whether the probe is evidence-only or pass/fail. Until then, C3 stays open.

## Recommended deterministic PR test

Use actual browser request events (Playwright) on the settled authenticated shell, not source-text assertions or a synthetic cache-only loader. Record request start/finish and request identity without cookies, response bodies, or credentials. Assertions should be relation/count based, never duration based:

- independent shell reads start before either peer finishes (for example the relevant `cycles.all`/`cycles.active` pair and, for admin, `users.all`/`teams.all` where that flow applies);
- two shell consumers of the same cycle pair cause only one request per pair member;
- after the shell is mounted and the applicable resource TTL is still warm, client navigation does not remount/refetch common session/cycle/admin shell data; count session separately because C1 deliberately does not cache session data and C8 expects one read per shared-shell lifetime;
- test only user-visible routes/interactions proven by final T15 behavior, with test data isolated.

The exact endpoint/count matrix must be finalized after T15 review so the PR contract follows its final route/UI implementation. Existing `cycles.test.ts` already covers its cache primitive with synthetic loaders, and `resourceCache.test.ts` proves generic cache behavior; neither is an actual browser waterfall, so do not treat them alone as C3 acceptance.

## Exact files to reserve

### PR waterfall

- `tests/test_e2e_playwright_spa_login_to_atlas.py` — add a distinct waterfall case using the existing isolated stack/role fixtures, **only after T15's full-run independent review and coordinator closure**. T15 owns this file now; do not merge T13 assertions into its active edit.
- `.github/workflows/ci.yml` — add the exact E2E module to the `frontend` path filter, or another equally narrow classifier rule, so a test-only edit triggers `spa-e2e`. Today `spa-e2e` and `spa-quality` run only when `frontend || shared || unclassified`; `tests/**` is classified as backend/runtime, so changing only the Python E2E file does not schedule the Playwright job. The job already installs Chromium and sets `OKR_RUN_PLAYWRIGHT_SPA_E2E=1`.
- Add one focused assertion to a dedicated CI/workflow wiring test (new `tests/test_spa_waterfall_ci_wiring.py`, or a narrowly coordinated existing CI matrix test) that a test-only E2E path schedules `spa-e2e`.

### Warmed-stack release probe

- New `scripts/probe_frontend_budget.py` — authenticated, bounded Playwright probe that writes a sanitized JSON report; keep the existing `scripts/diagnose_page_load.py` as offline trace analysis, not proof of a live browser waterfall.
- New `tests/test_frontend_budget_probe.py` — positive/negative report validation and command/wiring-safe behavior with synthetic fixtures; no network or secrets.
- `.github/workflows/darkube-prerelease.yml` — invoke the probe only in the protected `workflow_dispatch` / `verify_private` path after runtime validation and stack health/smoke readiness; use existing `WEB_URL` and protected synthetic credentials; upload a separate `darkube-prerelease-frontend-budget` artifact tied to `github.sha`/web build ID. Keep it out of ordinary PR CI, since PRs have no warmed provider stack or protected credentials.
- `tests/test_prerelease_workflow_contract.py` — assert the release probe runs only in the private dispatch path, receives required safe inputs, and uploads its report artifact. Do not satisfy the contract with a source-string-only check; assert job/step dependencies and artifact name/path.
- `docs/architecture/performance.md` — record the implemented metric, pinned conditions, invocation, output schema, and explicit live-evidence limitation. If release record retention requires linking the report from the strict evidence template, reserve `scripts/write_prerelease_evidence.py`, `tests/test_prerelease_evidence.py`, and `docs/saas/prerelease-evidence.md` as a separately reviewed schema extension; current writer rejects unknown fields. Prefer attaching the report as a named separate artifact until that schema change is necessary.

**No planned changes:** `spa-web/src/lib/resourceCache.ts`, shell/layout/hooks, T32/T35 PostgreSQL counters/fixtures, `scripts/slo_probe.py` (it is an API SLO probe, not a browser waterfall), generated API contracts, and T15 route assertions. If final behavior requires a frontend source adjustment, return it to T11/T12/T15 owner rather than broadening T13.

## Commands and expected artifacts

### Local/PR

Current focused T15 module command:

```powershell
$env:OKR_RUN_PLAYWRIGHT_SPA_E2E='1'
.venv\Scripts\python.exe -m pytest -q tests/test_e2e_playwright_spa_login_to_atlas.py -k request_waterfall
```

The PR job must run that focused case (or the complete existing module) after the new path-filter wiring. Existing `spa-quality` runs all Vitest tests, but a Vitest-only cache test is insufficient for the actual browser-waterfall contract. Also run the existing SPA suite/typecheck/build and the wiring test:

```powershell
npm run test --workspace spa-web
npm run typecheck --workspace spa-web
npm run build --workspace spa-web
.venv\Scripts\python.exe -m pytest -q tests/test_spa_waterfall_ci_wiring.py tests/test_prerelease_workflow_contract.py
```

### Release/warmed stack

No live command exists yet. The new workflow command should use the approved protected Darkube pre-release URL and synthetic credentials, e.g. `python -m scripts.probe_frontend_budget --base-url "$WEB_URL" --username "$PRERELEASE_SMOKE_USERNAME" --password "$PRERELEASE_SMOKE_PASSWORD" --build-id "$WEB_BUILD_ID" --output frontend-performance.json`. Do not log credentials/cookies or include private URL query values. Required artifact fields: commit/build ID; browser engine/version and viewport; observed stack readiness and UTC timestamp; safe route/data-access mode; cold/warm browser and application-cache conditions; sample count; page metric definition and raw/summary values; request count/order contract; safe `Server-Timing` duration summary; probe result and failure reason. Use the existing `scripts/slo_probe.py` parser only as a parsing reference for safe timing values.

Expected evidence: `frontend-performance.json` uploaded from the release workflow, correlated to the exact deployed commit/build manifest, plus a human approval/attachment in the release record. `docs/saas/release-go-no-go-checklist.md` already requires browser waterfall/layer timing and marks Performance NO-GO until measured. A passing probe does not clear unrelated provider backup, rollback, or operations-owner gates.

## Dependencies and conflict scan

- **T15:** full opted-in suite is 6/6 and independent review PASS; the E2E file is released to T13 for one new, separate waterfall case. Use its final route/UI state as the measured contract.
- **T12:** complete locally and reviewed; its shell/chunk changes are part of the target, not an invitation to change them in T13.
- **T11:** local cache tests pass, but remote PR #177/commit refresh and warmed deployment drill are still open. Do not trust the historical PR status. C8 drill includes navigation, polling, timer continuity, and post-mutation role freshness; capture with T13 only if coordinated, and do not conflate the two acceptance checklists.
- **CI/release workflow lane:** `.github/workflows/ci.yml`, `.github/workflows/darkube-prerelease.yml`, and workflow tests are shared with T07/T24/T27/T30/T32/T35. Coordinator reserves both workflow files for T13 now; T07/T27 are complete, T24/T30 are externally blocked, and T32/T35 lack real DSNs. No other packet may edit these workflows until T13 integration/review is complete.
- **T10:** complete; its former test/script slice included the E2E file but is closed. Keep new T13 helper tests in exact reserved files above.
- **T05:** current `docs/architecture/ARCHITECTURE_BACKLOG.md` already says the performance probe is not evidence and points to C1-C3/T13. Re-read after the artifact exists; make no historical wording claim now. Coordinate any edit with T05/docs steward.
- **External warmed stack:** T11 found no currently reachable warmed deployment; local availability does not prove a hosted Darkube stack. The release workflow needs its protected environment, URL, secrets, and an actually ready deployment. If unavailable, mark probe unavailable/not-run and keep C3 open; do not fabricate an artifact.

## Implementation order

1. Refresh T11's current PR #177 state before choosing what shell version to measure. PR #177 is merged at `3e35315c5ee9d21c7605e6f88a97d148ad3e1050`; C8's warmed-stack drill remains open.
2. Coordinator reserves the shared workflow lane; implement deterministic Playwright request assertions, narrow test-only CI classification, and the wiring test.
3. Implement probe/report schema with synthetic validation tests; confirm the owner-approved frontend metric/budget before calling any numerical result pass/fail.
4. Integrate into protected warmed-stack release workflow and add docs/wiring coverage. Run local checks; keep C3 open.
5. Run the release workflow against the approved warmed deployment and exact commit/build; archive the report with release evidence. Close C3 only after approval and successful artifact.
