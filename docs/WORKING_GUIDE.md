Documentation HQ: [README](../README.md)

# Working Guide

Use this as the compact starting point for continuing work. It answers three
questions: where the project stands, what to do next, and how to know it is done.

## Primary guide

- [docs/architecture/ENTERPRISE_SAAS_ROADMAP.md](architecture/ENTERPRISE_SAAS_ROADMAP.md)

This is the main roadmap and the source of intent.

## Status ledger

- [docs/architecture-status.md](architecture-status.md)

This is the source of truth for what is verified and what is open.

## Execution programme

- [docs/REMAINING_ENGINEERING_PLAN.md](REMAINING_ENGINEERING_PLAN.md)

This is the source of sequence: every open engineering issue, its dependencies,
and its acceptance test. Start here when you are ready to work.

| Workstream | Scope | Items | Size |
| --- | --- | --- | --- |
| A | Release and recovery integrity | A1 deploy CLI broken, A2 restore unreachable, A3 evidence gate not in CI, A4 control-plane contradiction, A5 attestation unverified | S-M |
| B | Document and governance truth | B1 evidence doc schema, B2 roadmap overclaim, B3 doc/code divergence, B4 stale perf ledger, B5 RLS gate naming, B6 quality baseline expiry, B7 unmerged work and worklog gap, B8 inert surfaces | S-M |
| C | Frontend performance and quality gates | C1 client caching and duplicate cycle fetch, C2 Suspense streaming, C3 page-load budget probe, C4 lint and typecheck, C5 in-app password change, C6 E2E coverage, C7 bff vitest config, C8 shell remounts on every navigation, C9 forced password change bypassable | S-L |
| D | Enterprise identity | D1 JWKS signature verification (gate), D2 OIDC login across BFF and SPA, D3 shared session revocation and dead `external_subject`, D4 BFF rate limit and origin, D5 SAML/SCIM/MFA/entitlements, D6 two incompatible session-token formats, D7 frozen `token_version`, D8 unverified user-resolution assumption | M-L |
| E | Provider-gated and external | E1 provider backup, E2 runtime adapter, E3 paired rollback, E4 k8s manifests, E5 owners and approval, E6 Phase 3 scope | blocked |

Start with Phase 1 of the plan. It has no external dependency.

## Current working posture

The repository-side architecture work is complete for its current scope. The
pre-SaaS simplification backlog is archived, and the browser-to-BFF-to-backend
trust boundary is verified for actor binding, forwarded role-claim enforcement,
and fail-closed session handling.

The remaining work splits into four parts, and only two of them are engineering
work that can be finished in this repository today:

1. **Integrity and truth fixes.** Defects and contradictions that are unblocked
   now: a broken release CLI, an unreachable restore path, a mandatory evidence
   gate that no CI job runs, an unverified attestation, and several documents
   that claim controls the code does not implement.
2. **Frontend performance corridor.** The P0-00 items for client caching, a
   Suspense-streamed shell, and a page-load budget probe are still open, and the
   repository has no JS/TS lint gate at all.
3. **Enterprise identity.** Phase 2 is not partially built; it is unbuilt. The
   backend contract exists and is exercised only by its own tests. There is no
   OIDC login in the SPA or the BFF, no ID-token signature verification, and
   session revocation is process-local and fails open.
4. **Provider-gated operational evidence.** Provider-backed backup and restore,
   measured RPO/RTO, a live paired rollback rehearsal, a named operations owner,
   and explicit real-data approval cannot be closed by writing code. They are
   tracked in Workstream E with named triggers.

Real customer data onboarding remains blocked until the provider-side gates pass
and `just saas-evidence` succeeds against externally verified evidence. That gate
is intentional and currently fails closed.

## Hard deadlines

| Date | Item | Consequence of missing it |
| --- | --- | --- |
| 2026-11-15 | Quality gate baseline item QG-002 (`docs/QUALITY_GATE_BASELINE.md`) | On 2026-11-16 `scripts/check_quality_gate_baseline.py` fails. It is an `always_run` pre-commit hook and a CI gate, so every commit and every CI run fails until QG-002 is retired or re-dated with a fresh rationale. |

The earlier 2026-09-30 deadline covering QG-001 and QG-002 was resolved on
2026-09-20 under B6. QG-001 was closed by expanding the Ruff format check to
repo scope, so its cliff no longer exists; QG-002 was re-dated to 2026-11-15 with
a staged burn-down recorded in `docs/QUALITY_GATE_BASELINE.md`.

## Decision rule

When unsure, follow this order:

1. Roadmap: the source of intent.
2. Architecture status ledger: the source of truth for current state.
3. Remaining engineering plan: the source of sequence.
4. Targeted security or operational doc.
5. Code and tests.

## Security and boundary references

- [docs/bff-security-review.md](bff-security-review.md)
- [docs/bff-boundary-adr.md](bff-boundary-adr.md)
- [docs/architecture-boundaries.md](architecture-boundaries.md)
- [ADR-001 multi-tenant data access boundary](ADR-001-multitenant-data-access-boundary.md) - rejected; single-tenant isolation is the only supported model

## Release and operational gates

- [docs/saas/release-go-no-go-checklist.md](saas/release-go-no-go-checklist.md)
- [docs/saas/prerelease-runbook.md](saas/prerelease-runbook.md)
- [docs/QUALITY_GATE_BASELINE.md](QUALITY_GATE_BASELINE.md)

## Known environment constraints

These are local tooling facts, not product defects. They cost time to rediscover.

- **`uv` cache in a locked-down sandbox only.** If `uv run` fails with
  `Failed to initialize cache at ...\uv\cache` and an access-denied error, point
  `$env:UV_CACHE_DIR` at a path inside the workspace. This is a local sandbox
  workaround, not a repository convention: nothing in the repo sets or documents
  `UV_CACHE_DIR`, so do not add it to config templates or CI.
- **Denied piped stdio.** Spawning a child process with piped stdio is denied in
  the restricted sandbox. This is reproducible:
  `node -e "require('node:child_process').spawnSync(process.execPath,['-e','1'],{stdio:'pipe'})"`
  returns `EPERM`. Vitest's default pool is `forks`, which needs piped stdio, so
  `npm test` (vitest) cannot start workers and neither can `next build` or
  `npm run check:gen:api`. The tooling itself is installed and fine —
  `spa-bff/node_modules/.bin/vitest` exists. `npm run typecheck` in `spa-web` and
  `npm run build` in `spa-bff` (its typecheck) both pass. Treat CI as the
  authoritative signal for the blocked commands.
- **pytest temp directories.** A stale or unwritable pytest basetemp causes mass
  `PermissionError [WinError 5]` errors that look like test failures. Pass an
  explicit writable `--basetemp` inside the workspace before concluding a suite
  is broken.
- **Generated artifacts.** `spa-bff/src/allowlist.ts` is generated from
  `spa-bff/src/route-policy.json` validated against the OpenAPI artifact. Never
  hand-edit it; run `python scripts/generate_bff_allowlist.py` and then
  `just generate-api`.
- **Documentation gates.** Every tracked Markdown file needs a
  `Documentation HQ: [README](...)` backlink, LF endings, no trailing whitespace,
  and a final newline. `scripts/check_docs_hq_links.py` runs as an `always_run`
  pre-commit hook.
