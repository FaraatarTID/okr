# T12 — Independent review

Verdict: **PASS**

## Scope reviewed

Reviewed T12 against `task-T12-brief.md` and C2 acceptance, focusing on the
shell access decision, admin role/tab policy, forced-password redirect,
deep-link behavior, deferred panels, and App Router boundary placement. No
implementation or shared-ledger files were edited.

## Findings

The first review pass found a blocking manager-tab flash: a manager on
`mode="admin"` with `adminTab="ai"` was considered ready until the existing
effect changed the tab to Cycles. This allowed one render of a disallowed
admin tab. The implementation fixed the decision to require either admin role
or manager role plus `adminTab === "cycles"`. I independently confirmed that
the new regression test covers this pre-effect case and that manager/Cycles
and admin access remain allowed. No remaining blocking findings.

The `AtlasShell` render returns the access status gate before protected chrome
when access is unresolved. The hook also keeps admin data fetches behind the
same readiness decision. Anonymous users continue to the login route, while
forced-password users are routed through `forcedPasswordChangeLocation` with
the current pathname and query string. The deep-link bootstrap and its focused
tests remain present and unchanged.

The ten mode/large panels use `next/dynamic` with local pending UI. The
deferred-panel test holds a panel import unresolved and confirms that shell
navigation remains usable while it loads. The production `(shell)` manifest
contains 10 async module IDs and 10 distinct chunk files; all 10 files exist.

`(shell)/error.tsx` is correctly scoped to shell page/child errors; the parent
`app/error.tsx` provides the boundary around `(shell)/layout.tsx`, which a
same-segment error boundary cannot catch. `app/not-found.tsx` supplies the
unknown-route recovery UI. The build registered `/_not-found` and the client
manifest includes both the shell and parent error modules for shell routes.

## Verification

- Focused Vitest: **39 passed** across six T12 files.
- `npm --prefix spa-web run typecheck`: passed.
- `npm --prefix spa-web run build`: passed; Next generated 16 static pages,
  including `/_not-found`.
- `(shell)/page/react-loadable-manifest.json`: 10 async IDs, 10 distinct
  chunks, 10/10 chunk files present.

Vitest emitted the existing Vite `configLoader: 'native'` compatibility
warning. It did not affect the passing run.
