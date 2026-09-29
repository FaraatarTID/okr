Documentation HQ: [README](../../../README.md)

# T11 verification report — cache and shared shell

## Local verification

Read-only inspection found the C1 cache implementation already present in
`spa-web/src/lib/resourceCache.ts`, `cycles.ts`, and `adminResources.ts`.
Session data is deliberately excluded from caching. Existing behavior covers
TTL, in-flight deduplication, failure eviction, bypass/write-through, mutation
reseeding, restore clearing, and sign-out clearing. C8 structural tests cover
shared shell node identity and route ownership, but do not establish navigation
and polling behavior on a warmed deployment.

The focused command from T11's plan passed: 12 test files, **85 passed**. Vitest
reported its existing Vite `configLoader: 'native'` warning. No product code was
changed in T11.

## Fresh remote and browser evidence — 2026-09-27

- `gh pr view 177` confirms PR #177 is merged at `3e35315c5ee9d21c7605e6f88a97d148ad3e1050` (merged 2026-09-20). The PR's listed CI, SPA E2E, backend-quality, spa-quality, documentation, and CI-result checks all report success. This refreshes the PR/commit question only; it does not establish deployment or current branch-protection state.
- The repository's GitHub deployments API returned an empty list. This shows no GitHub-managed deployments were recorded for the repository at query time; it does not rule out a deployment hosted elsewhere.
- After the T23 E2E fixture was corrected to enable signed internal requests and use its task-owned SQLite database for security state, the real browser `request_waterfall` case passed locally: **1 passed, 9 deselected in 24.36s**. The full opted-in E2E module passed **10 tests in 212.87s**. A fresh coordinator-context rerun of the focused case also passed **1 passed, 9 deselected in 24.36s**. Backend logs show login, private session registration, and authenticated reads returning 200.
- That browser case navigates repeatedly between Dashboard and Admin on a warmed local stack, asserting that session, cycle, users, and teams request counts do not increase. It is useful local C8 evidence, but it does not instrument snapshot/dashboard poll timers or prove role freshness after a mutation.

## Current checkout and open evidence

- Local `HEAD`: `0c297411db024a5a482c23eb7261b92f9eeeb6f8`.
- `git status --short` shows authorized in-progress packet changes and newly
  created local plan/report files; this is not a clean PR snapshot.
- The merged PR state and listed checks are now refreshed above. The checkout
  is still dirty with in-progress packet changes and is not a clean PR snapshot.
- No warmed deployment was available in GitHub's deployment records; no
  non-GitHub target was specified. The local browser run does not establish
  deployment behavior.
- Snapshot/dashboard polling continuity and post-mutation role freshness remain
  unverified by the browser case.

T11 remains open for polling continuity and role-freshness evidence from an
approved warmed stack. No cache or session-freshness claim is promoted from the
local component suite or E2E fixture to deployment acceptance.
