Documentation HQ: [README](../../../README.md)

# T16 — Runtime version and lint findings

## Scope and acceptance

Source: C4 in `docs/REMAINING_ENGINEERING_PLAN.md`; packet: T16 in `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md`.

- Inspect the exact Node runtime represented by the digest-pinned BFF base image and the Node runtime configured for CI before editing `spa-bff/package.json` `engines.node`.
- Run the whole JavaScript lint gate and inspect every finding against documented supported behavior.
- Wire a finding only when a supported flow requires it; remove dead code only when that can be established without erasing a feature/product decision.
- Do not change either npm lockfile, shared workflows, or `tests/test_e2e_playwright_spa_login_to_atlas.py`.
- Record evidence and any remaining owner/external gate. No rule suppression is allowed as a way to reduce the warning count.

## Evidence collected

- `spa-bff/Dockerfile` pins `node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32` in both stages. The official Docker Hub layer record for this exact digest exposes `ENV NODE_VERSION=22.23.2`: <https://hub.docker.com/layers/library/node/22-alpine/images/>.
- The local Docker daemon cannot be queried in this environment (permission denied on the Docker Engine named pipe). The official image record provides the digest-specific image metadata independently.
- All `actions/setup-node@v6` entries in `.github/workflows/ci.yml` and `.github/workflows/darkube-prerelease.yml` configure `node-version: "22"`. No hosted run metadata is available in the checkout to prove the exact patch resolved by CI.
- `spa-bff/package.json` still declares `engines.node: ">=20"`; it was not changed while the exact CI patch remained unverified.

## Lint baseline

`npm exec eslint -- spa-web spa-bff --format stylish` completed with exit code 0, 0 errors, and 9 warnings. Eight correspond to the open product/wiring questions recorded in C4/F3; the ninth is an exhaustive-deps report for the derived `canManageCycles` local in `useShellAccessControl.ts`. No lint suppressions were added.

## File reservation

`tests/test_e2e_playwright_spa_login_to_atlas.py` belongs to T15 and remains untouched. While T15's browser run is active, avoid edits to its shared shell/UI modules. Finish any behavior-neutral lint cleanup only after T15 reports its browser run and review complete.
