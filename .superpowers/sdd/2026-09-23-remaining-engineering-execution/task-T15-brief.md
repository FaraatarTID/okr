# T15 — Role-parameterized route and surface E2E

## Objective

Implement the reconciled C6 acceptance in `docs/REMAINING_ENGINEERING_PLAN.md`:
prove actual route and UI behavior with the existing isolated Playwright stack,
including role policy, direct-load deep-link state, Inspector alignment, and
rendered RTL text. Do not invent paths for alignment or RTL.

## Exact ownership

- `tests/test_e2e_playwright_spa_login_to_atlas.py` only.
- T15 report/snapshot/review artifacts under this SDD directory.

Do not edit app code, T14 password-change files, workflows, other tests, route
ownership tests, database migrations, or the shared progress ledger. T14 must
not edit this E2E file.

## Acceptance

- Using the existing `e2e_admin`, `e2e_manager`, and `e2e_member` fixtures, visit
  `/dashboard`, `/daily`, `/timeline`, and `/retrobox` as each role and assert
  route-specific visible UI (not only `page.url` or source strings).
- Exercise Admin users/teams/backup/audit tabs as admin; assert manager access
  remains Cycles-only and direct member navigation to `/admin` is denied or
  redirected, not merely hidden in navigation.
- Direct-load a supported deep link with a cycle/node selection and assert the
  selected state in rendered UI after reload.
- Verify alignment and RTL via actual rendered Inspector/work-history or
  analysis content. Seed an appropriate RTL string if existing fixture data
  cannot demonstrate it. Do not assert only a helper's return value.
- Preserve the unique temporary SQLite database per E2E run and do not touch a
  user/shared database. Keep tests serial unless their data is isolated.
- Use test-first changes. Run the opted-in focused E2E command and report any
  missing local browser/runtime prerequisite honestly; run focused static checks
  for the edited test.

## Verification command

```powershell
$env:OKR_RUN_PLAYWRIGHT_SPA_E2E='1'
.venv\Scripts\python.exe -m pytest -q tests/test_e2e_playwright_spa_login_to_atlas.py
```

The module starts backend, BFF, Next.js, and a worker. Do not run the full
repository suite for this packet.
