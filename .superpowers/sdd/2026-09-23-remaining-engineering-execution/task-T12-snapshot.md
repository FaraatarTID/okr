Documentation HQ: [README](../../../README.md)

# T12 re-review snapshot

Base: current shared checkout. Scope is T12 only; the shared progress ledger is
untouched.

| File | Re-review focus |
| --- | --- |
| `spa-web/src/components/atlas-shell/useShellAccessControl.ts` | `accessReady` is the single pre-render decision. It requires hydrated auth, a user with no forced password change, and current-mode permission. For admin mode, admins may access every tab and managers may access only `cycles`. Admin data effects wait for readiness. |
| `spa-web/src/components/atlas-shell/useShellAccessControl.test.ts` | Manager + `admin` + `ai` now asserts `accessReady === false` while the existing effect resets the tab to `cycles`; manager + Cycles and admin controls remain allowed. |
| `spa-web/src/components/AtlasShell.tsx` | `ShellAccessGate` prevents protected chrome from rendering until the hook grants access; ten panel imports remain `next/dynamic`. |
| `spa-web/src/components/atlas-shell/ShellAccessGate.test.tsx` | Denied readiness renders no navigation; allowed readiness does. Deferred `next/dynamic` test holds the panel loader unresolved and confirms the workspace navigation control remains available. |
| `spa-web/src/app/(shell)/loading.tsx`, `error.tsx`, `spa-web/src/app/error.tsx`, `spa-web/src/app/not-found.tsx` | Loading, page-level retry, parent layout recovery, and unknown-route recovery. Same-segment error cannot catch `(shell)/layout.tsx`; parent `app/error.tsx` is required. |
| `task-T12-report.md`, `task-T12-review.diff` | Commands, results, scoped source changes, and review evidence. |

## Verification after manager-tab fix

- RED: `npm --prefix spa-web test -- src/components/atlas-shell/useShellAccessControl.test.ts` failed as expected: manager + admin + AI tab returned `true` instead of `false`.
- GREEN: same focused hook test: 14 passed.
- Focused T12 Vitest: 6 files, 39 tests passed.
- `npm --prefix spa-web run typecheck`: pass.
- `npm --prefix spa-web run build`: pass; 16 static pages generated, including `/_not-found`.
- Generated shell page manifest: 10 async module IDs, 10 distinct chunks, 10/10 chunk files present.

The intentional Vite native-config compatibility warning remains in Vitest
output. No Git index, branch, worktree, or commit operation was attempted.
