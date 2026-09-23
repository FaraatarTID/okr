# T12 — Route streaming and code splitting

## Objective

Implement the authoritative C2 plan: add route loading/error/not-found handling
and defer the ten mode/large panels currently eagerly imported by
`AtlasShell.tsx`. The shell must be useful while snapshots/panels load, while
access checks must prevent authenticated chrome from flashing for an anonymous,
forced-password-change, or mode-disallowed user. Preserve login redirect,
admin policy, forced-password flow, and pathname/query-driven deep-link
bootstrap.

## Exact owned files

- `spa-web/src/components/atlas-shell/AtlasShell.tsx`
- `spa-web/src/components/atlas-shell/useShellAccessControl.ts` and its focused
  test, if the render-level access-ready decision must be exposed from the
  existing redirect hook.
- The ten panel modules it currently imports eagerly: `AdminModePanel`,
  `DashboardLeadershipPanel`, `TimelineModePanel`, `WeeklyModePanel`,
  `DailyModePanel`, `RitualModePanel`, `RetroboxModePanel`,
  `AtlasFocusMapPanel`, `AtlasModeControlsPanel`,
  `InspectorAiAssistPanel` (components and any directly colocated tests)
- New route UI: `spa-web/src/app/(shell)/loading.tsx`,
  `spa-web/src/app/(shell)/error.tsx`, `spa-web/src/app/error.tsx`, and
  `spa-web/src/app/not-found.tsx`, as justified by Next.js boundary placement.
- New focused T12 tests under `spa-web/src/components/atlas-shell/` or
  `spa-web/src/app/`.

Do not edit package manifests/lockfiles, `layout.tsx`, C8 route-ownership or
layout identity tests unless an exact necessary regression is demonstrated.
Do not take T15 E2E tests or T13 workflow files. T11 had no product-code edits.

## Acceptance

- Mode and large panels are code-split and load on demand; a deferred panel does
  not prevent the authenticated shell/navigation from becoming usable.
- Route loading, error recovery, and not-found UI are present at boundaries
  that actually wrap their intended components. An error boundary in the same
  segment cannot catch that segment's layout, so validate placement in build.
- Authenticated shell chrome renders only after access readiness establishes
  that a hydrated user is allowed to see the current mode. Preserve admin
  manager/member policy and forced-password `return_to` semantics.
- Anonymous, forced-change, and denied-admin tests prove no protected chrome
  flashes before redirect; allowed user and deep-link controls continue to
  work.
- Add a deferred-chunk/panel test that proves the shell remains usable while
  that panel resolves. Route failures have a retry/recovery control.
- Run focused Vitest, `npm --prefix spa-web run typecheck`, and
  `npm --prefix spa-web run build`. Inspect App Router build output and
  generated route/types; report existing environment-only caveats explicitly.

## Workflow

Use test-first changes and keep the auth/access decision outside lazy panel
boundaries. Preserve user changes. `.git` is read-only: no branches, worktrees,
index writes, or commits. The separate T15 route-level E2E packet follows T12.
