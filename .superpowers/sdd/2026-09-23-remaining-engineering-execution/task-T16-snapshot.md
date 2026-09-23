# T16 execution snapshot

Date: 2026-09-23

## Runtime facts

| Surface | Evidence | Exactness |
|---|---|---|
| BFF image | `spa-bff/Dockerfile:1,16` uses `node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32`. Official Docker Hub layer details for that digest show `ENV NODE_VERSION=22.23.2`: <https://hub.docker.com/layers/library/node/22-alpine/images/>. | Exact image Node version observed: 22.23.2. |
| CI | `.github/workflows/ci.yml:236,399,488,563` and `.github/workflows/darkube-prerelease.yml:148` configure `actions/setup-node@v6` with `node-version: "22"`. | Major line is observed; exact hosted patch is unavailable in the local checkout. |
| Manifest | `spa-bff/package.json` declares `engines.node: ">=20"`. | Unchanged under the exact CI runtime gate. |

Local Docker image inspection failed because the Docker Engine named pipe is inaccessible. Official digest-specific image metadata supplied the image version, so only the exact hosted CI patch remains unobserved.

## Lint evidence

Command: `npm exec eslint -- spa-web spa-bff --format stylish`

Exit code: 0. Findings: 0 errors, 9 warnings.

1. `spa-web/src/components/AtlasShell.tsx:208` — `cycleResolvePending`.
2. `spa-web/src/components/AtlasShell.tsx:455` — `adminBackupFile` destructured binding.
3. `spa-web/src/components/AtlasShell.tsx:1182` — `canCreateForContext` destructured binding.
4. `spa-web/src/components/AtlasShell.tsx:1303` — unreferenced recursive `renderMindmapTreeNode`.
5. `spa-web/src/components/atlas-shell/InspectorAlignmentPanel.tsx:61` — unused `alignmentDirection` prop.
6. `spa-web/src/components/atlas-shell/InspectorAlignmentPanel.tsx:64` — unused `onAlignmentDirectionChange` prop.
7. `spa-web/src/components/atlas-shell/useAdminActions.ts:121` — unused `canMutateCycle` callback.
8. `spa-web/src/components/atlas-shell/useInspectorAuxData.ts:66` — unused `setObjLinkPending` setter.
9. `spa-web/src/components/atlas-shell/useShellAccessControl.ts:99` — exhaustive-deps on derived `canManageCycles`.

No code, workflow, package manifest, lockfile, or T15 browser-test file was changed. The first eight remain subject to the existing C4/F3 feature or wiring decisions; the ninth is currently behavior-masked by existing dependencies (`isAdmin`, `isManager`, `user`) and does not show a present stale-effect defect.

## Ownership / integration

- T15 browser rerun was active during inspection; no shared SPA component or hook was edited.
- Shared progress ledger was not edited.
- Full disposition is in [task-T16-report.md](task-T16-report.md); packet scope is in [task-T16-brief.md](task-T16-brief.md).
