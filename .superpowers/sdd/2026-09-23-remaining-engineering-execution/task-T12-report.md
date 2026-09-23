Documentation HQ: [README](../../../README.md)

# T12 — Route streaming and code splitting

Status: implementation ready for independent review; packet not marked complete.

## Implemented

- Replaced the ten eager AtlasShell panel imports with `next/dynamic` imports:
  `AdminModePanel`, `DashboardLeadershipPanel`, `TimelineModePanel`,
  `WeeklyModePanel`, `DailyModePanel`, `RitualModePanel`, `RetroboxModePanel`,
  `AtlasFocusMapPanel`, `AtlasModeControlsPanel`, and `InspectorAiAssistPanel`.
  Each deferred panel has a local accessible pending state. Navigation and the
  rest of the shell remain rendered while the selected panel chunk resolves.
- Added one access decision to `useShellAccessControl`: access is ready only
  after auth hydration, with a user, without a forced password change, and when
  the user may access the selected mode and admin tab. Admins can access every
  admin tab; managers can access only the `cycles` tab; members cannot access
  admin mode. Admin resources, health, and audit fetches also wait for this
  decision.
- Wrapped protected shell chrome in `ShellAccessGate`. Until access is ready,
  the gate only renders a status panel. The shell still delegates anonymous and
  forced-password routing to the existing redirect behavior, preserving the
  current `return_to` path and query. Managers retain Cycles-only admin access;
  members are denied admin mode before any shell chrome can render.
- Added `(shell)/loading.tsx`, `(shell)/error.tsx`, `app/error.tsx`, and
  `app/not-found.tsx`, with accessible pending/error states, retry controls, and
  a workspace recovery link.

## Boundary placement

`app/(shell)/error.tsx` catches failures from shell pages and child segments.
It cannot catch the `(shell)/layout.tsx` that shares its segment. The parent
`app/error.tsx` is the boundary that wraps and can catch the shell layout. The
production build completed with both error boundaries and the not-found route
registered. The root layout itself remains outside `app/error.tsx` as required
by App Router boundary semantics.

## Verification

- RED/GREEN access tests: new access-readiness expectations first failed because
  the hook returned no `accessReady`; they pass with the single hook decision.
  A follow-up regression test reproduced the manager tab flash: the manager
  with `mode="admin"` and `adminTab="ai"` returned `true` before the fix. The
  readiness decision now includes that tab permission, and the case returns
  `false` while the existing effect resets the tab to `cycles`.
- RED/GREEN route UI tests: initially failed because route UI modules did not
  exist; all four now pass, including retry and not-found recovery controls.
- Shell access gate tests prove anonymous, forced-password, and denied-admin
  states render no navigation; allowed access renders it. A deferred
  `next/dynamic` panel test proves the navigation button stays available while
  the module promise is pending and after it resolves.
- Focused Vitest: **39 passed** across six files covering route UI, shell gate,
  access policy, deep-link bootstrap, and admin/Atlas controls.
- `npm --prefix spa-web run typecheck`: pass.
- `npm --prefix spa-web run build`: pass. Next reported the expected route set,
  including `/_not-found`. The generated `(shell)/page/react-loadable-manifest.json`
  has **10 async module IDs**, maps them to **10 distinct client chunk files**,
  and all ten files exist. The page client manifest includes `app/error.tsx`
  around the `(shell)/layout.tsx` client tree.

Vitest prints the existing Vite `configLoader: 'native'` compatibility warning.
One earlier isolated test invocation also printed an unreproduced localhost
`ECONNREFUSED`; the final focused run passed without that output.

## Scoped files

- Modified: `spa-web/src/components/AtlasShell.tsx`,
  `spa-web/src/components/atlas-shell/useShellAccessControl.ts`, and its test.
- Added: shell loading/error UI, app error/not-found UI, and focused route UI and
  access-gate tests.
- No panel module, package manifest, route ownership test, workflow, layout, or
  T15 E2E test was changed.
- `task-T12-review.diff` contains the scoped patch, and
  `task-T12-snapshot.md` records the re-review scope and verification. The
  shared progress ledger was not edited. No branch, worktree, index, or commit
  operation was attempted.
