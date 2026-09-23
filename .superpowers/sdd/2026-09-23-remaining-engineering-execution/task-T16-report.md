# T16 report — Runtime version and lint findings

## Result

T16 is partially complete. The exact BFF image Node version is now observable from the official Docker Hub layer record for the digest in `spa-bff/Dockerfile`: Node `22.23.2`. CI config specifies only the major line (`node-version: "22"`), and no hosted run metadata is available to confirm the resolved patch. Per the packet gate, `engines.node` remains unchanged at `>=20` pending exact CI evidence.

The whole-package lint gate runs successfully with 0 errors and 9 warnings. No suppressions were introduced. Eight warnings are the already tracked product/wiring decisions in canonical F3; the ninth is an exhaustive-deps warning for `canManageCycles`, a local derived from `isAdmin` and `isManager` in `useShellAccessControl.ts`.

## Per-finding disposition

| Finding | Disposition |
|---|---|
| `AtlasShell.tsx:208` — `cycleResolvePending` | Pending-state rendering is not currently read. Do not remove the cycle-resolution flow based on this warning alone; inspect the user's supported loading behavior and decide whether to display the pending state. |
| `AtlasShell.tsx:455` — `adminBackupFile` binding | Hook state is consumed internally by the restore handler; only the parent destructured binding is unused. Safe binding cleanup appears possible, but defer while T15's shared-shell browser run is active. |
| `AtlasShell.tsx:1182` — `canCreateForContext` binding | JSX separately computes the rendered boolean from `createContext`; parent binding is unused. Safe binding cleanup appears possible, but defer while T15 is active. |
| `AtlasShell.tsx:1303` — `renderMindmapTreeNode` | Function only recurses into itself and has no external entry point. Deleting it removes an unrendered UI capability; preserve pending an explicit feature decision rather than treating lint as that decision. |
| `InspectorAlignmentPanel.tsx:61,64` — alignment direction props | The component accepts but does not render direction controls. The architecture documents objective links to parent Goals and child KRs, while the hook's create handler uses this direction. This appears to leave a documented flow inaccessible; T15 owns rendered alignment coverage, so coordinate the control/UI change with that packet after its current browser run. |
| `useAdminActions.ts:121` — `canMutateCycle` | The callback is unused. This is adjacent to manager cycle mutation boundaries, so do not delete or wire based on lint alone; confirm the server-side ownership gate and rendered supported behavior first. |
| `useInspectorAuxData.ts:66` — `setObjLinkPending` | No call raises the pending flag. Adding a pending lifecycle to cross-hierarchy link mutations is plausible but changes UI behavior; coordinate with the alignment flow and T15 assertions. |
| `useShellAccessControl.ts:99` — missing `canManageCycles` dependency | No behavioral dependency defect found. `canManageCycles` is exactly `isAdmin || isManager`; both booleans and `user` are effect dependencies, and AtlasShell derives both role booleans only from `user.role`. The effect therefore re-runs for every change that can alter `canManageCycles`. Including the derived value would make the declaration more robust to future derivation changes but is not needed to preserve current behavior. Defer even that behavior-neutral cleanup until T15's live browser rerun completes. |

The three potentially cleanup-only bindings and behavior-neutral dependency fix are not yet edited because T15's real browser run is active against this shell. The alignment direction control is the strongest documented-flow candidate for wiring, but it shares T15's rendered alignment surface and is deferred until that run/review ends.

## Verification

- `npm exec eslint -- spa-web spa-bff --format stylish`: exit 0, 0 errors, 9 warnings.
- Local `docker image inspect` could not run because Docker Engine access is denied. This did not block digest-specific runtime observation through the official image metadata.
- No tests were added or run in this packet. No npm lockfile, workflow, or T15-owned test file was edited.

## Remaining gates

1. Obtain hosted CI job output (or pin CI to an exact patch in a separately authorized workflow change) to establish the exact CI runtime. Then align `engines.node` with both CI and image support.
2. After T15 finishes browser execution and independent review, integrate any shared UI lint fixes serially. Keep unresolved product choices open rather than deleting features to make lint green.
