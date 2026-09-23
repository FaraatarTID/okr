Documentation HQ: [README](../../../README.md)

# T06 — Fastify advisory and lockfile repair report

Status: BLOCKED before implementation. No npm manifests or lockfiles were edited.

## Execution-time advisory check

Checked the Fastify project’s primary GitHub advisories on 2026-09-23:

- [GHSA-w2qp-rph6-63g4](https://github.com/fastify/fastify/security/advisories/GHSA-w2qp-rph6-63g4): affected versions `< 5.12.1`; patched version `5.12.1`. The issue is root primitive body schema coercion mismatch.
- [GHSA-3m5p-2c4r-xxw2](https://github.com/fastify/fastify/security/advisories/GHSA-3m5p-2c4r-xxw2): affected versions `>= 5.8.3, < 5.12.1`; patched version `5.12.1`. The issue is X-Forwarded-* spoofing with numeric `trustProxy` hop counts.
- The [Fastify releases page](https://github.com/fastify/fastify/releases) lists stable release `v5.12.5` as latest at the time checked. This is above both patched-version floors, but was not installed or validated in this blocked run.

## Genuine fresh-clone attempt

The required fresh full clone was attempted once, without using a worktree or shared Git directory:

```powershell
$cloneRoot = Join-Path $env:TEMP ('okr-t06-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cloneRoot | Out-Null
git clone --no-hardlinks --origin origin https://github.com/FaraatarTID/okr.git (Join-Path $cloneRoot 'repo')
```

Result:

```text
CLONE_ROOT=C:\Users\MIRSHE~1\AppData\Local\Temp\okr-t06-257240192f6847f589aafe0d97e7a01f
Cloning into 'C:\Users\MIRSHE~1\AppData\Local\Temp\okr-t06-257240192f6847f589aafe0d97e7a01f\repo'...
fatal: unable to access 'https://github.com/FaraatarTID/okr.git/': Failed to connect to github.com port 443 after 125 ms: Could not connect to server
```

The clone stopped before creating a repository. Per T06’s stop condition, I did not retry in the same network environment, use the shared checkout, regenerate package locks by hand, or attempt npm dependency changes.

## Current checkout observation (read-only)

`spa-bff/package.json` declares `fastify: ^5.6.1`; both `spa-bff/package-lock.json` and root `package-lock.json` contain `fastify` `5.8.5`. Git status for those four package files showed no changes from this task.

## Acceptance evidence not obtained

Because the fresh clone could not be created, none of the required dependency resolution or verification gates ran: npm lockfile regeneration, `npm ci`, BFF tests/build/typecheck, audit, and repeat verification from an unrelated clean clone. The historical stale lockfile failure remains un-reproduced in this attempt. T06 remains blocked until a network-enabled environment can provide the genuine fresh full clone and unrelated clean-clone verification.

## Follow-up — authorized fresh clone and clean-clone verification

Status: **dependency repair and required local verification passed in an authorized full clone; no changes were made to the shared checkout's npm files.** This follow-up supersedes the earlier blocked status for T06 while retaining that original failed clone attempt as historical evidence.

### Clone and advisory evidence

An authorized, independent full clone was supplied at:

```text
C:\Users\MIRSHE~1\AppData\Local\Temp\okr-t06-escalated-26700a1ec6254a329898957bf0781651\repo
```

Git reported dubious ownership for this clone. Commands used `git -c safe.directory=<clone path>` per invocation; no global Git configuration was changed. The clone contained `origin/SPA-BFF-clean` at the shared workspace baseline `0c297411db024a5a482c23eb7261b92f9eeeb6f8`, and that branch was checked out. Its starting worktree was clean.

Execution-time checks on 2026-09-23 against the primary Fastify GitHub advisories confirmed both prior issues are patched in `5.12.1`: [GHSA-w2qp-rph6-63g4](https://github.com/fastify/fastify/security/advisories/GHSA-w2qp-rph6-63g4) and [GHSA-3m5p-2c4r-xxw2](https://github.com/fastify/fastify/security/advisories/GHSA-3m5p-2c4r-xxw2). The official [Fastify releases page](https://github.com/fastify/fastify/releases) listed `v5.12.5` as the latest stable 5.x release. The repair selected `5.12.5`.

### npm-generated dependency changes

Using Node `v22.21.0` and npm `10.9.4`, npm updated `spa-bff/package.json` to `fastify: ^5.12.5` and regenerated both lockfiles. The final root workspace lock resolves `node_modules/fastify` to `5.12.5`; the standalone BFF lock resolves `node_modules/fastify` to `5.12.5`. No lockfile contents were hand-edited.

One workspace detail is recorded for future reproduction: the initial root `npm install --workspace spa-bff fastify@^5.12.5 --package-lock-only` and `npm update --workspace=spa-bff fastify --package-lock-only` returned success but left the root lock's old `5.8.5` entry in place. A subsequent npm uninstall of the workspace dependency followed by npm install of `fastify@^5.12.5` regenerated the root workspace lock correctly and hoisted Fastify to `5.12.5`. This was all performed through npm. Both final clean installs below verified the resulting manifest/lock combination from scratch. The standalone BFF lock was regenerated through npm as well.

### First-clone verification

In the authorized clone:

- `npm ci` — passed; 339 packages added, 342 audited, zero vulnerabilities.
- `npm ci --prefix spa-bff --workspaces=false` — passed; 120 packages added, 121 audited, zero vulnerabilities.
- `npm test` — passed; BFF 11 files / 86 tests and SPA web 48 files / 234 tests.
- `npm run build` — passed for both workspaces; Next.js production build completed.
- `npm run typecheck` — passed for both workspaces.
- `npm audit` — passed, zero vulnerabilities.
- `npm audit --prefix spa-bff --workspaces=false` — passed, zero vulnerabilities.
- `git diff --check` — passed.

An isolated local commit, `7cc121259d4da321edbe1ce97dedcfce342a0258`, contains only the two lockfiles and `spa-bff/package.json`; it was not pushed.

### Second full clean-clone verification

A second full clone was created with `git clone --no-hardlinks` at:

```text
C:\Users\MIRSHE~1\AppData\Local\Temp\okr-t06-cleanverify-7cc1212
```

It checked out the isolated commit above, had its own `.git` directory and a clean worktree, and started without `node_modules`.

- Root `npm ci` and standalone BFF `npm ci --prefix spa-bff --workspaces=false` — passed; zero vulnerabilities reported by each install.
- Root `npm test` — passed; 11 BFF files / 86 tests and 48 SPA web files / 234 tests.
- Root `npm run build` — passed for both workspaces.
- Root `npm run typecheck` — passed for both workspaces.
- Root and standalone BFF `npm audit` — passed, zero vulnerabilities each.

The initial default-sandbox clone failure recorded above is retained as historical evidence. Network access for npm registry requests required the authorized escalation; no registry/runtime/ACL blocker remained after that authorization. The temporary clones were left in place. The dependency change is ready for the integration steward to transfer from commit `7cc121259d4da321edbe1ce97dedcfce342a0258` into the shared checkout under the serialized lockfile lane.
