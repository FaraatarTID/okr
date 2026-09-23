# T05 implementation report — roadmap and backlog truth

Status: implementation ready for independent review; packet not marked complete.

## Scope and source

Edited only `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md` and
`docs/architecture/ARCHITECTURE_BACKLOG.md`. Used the current
`docs/REMAINING_ENGINEERING_PLAN.md` B2/B4/C1-C3/C8 rows, the T05 execution
packet, and `docs/ADR-001-multitenant-data-access-boundary.md` as decision
sources. The diff snapshot is `task-T05-review.diff`. No Git index, branch,
worktree, or commit write was attempted.

## Changes

- Roadmap lines 9, 48-54: linked the authoritative remaining-work register and
  replaced the claim that only operational verification remains. The status
  names open repository workstreams A-D, read-path/P0 work, the absent OIDC
  flow, and the distinct provider, owner, real-data, and recovery evidence
  gates. It does not assert that local evidence proves a production drill.
- Roadmap lines 25, 35, 65, 124, 147-153, 177, 196-197: aligned the isolation language
  with ADR-001. Shared-database tenancy and tenant-isolation RLS are rejected;
  security investigation scope is per dedicated environment. Existing
  PostgREST hardening RLS is not characterized as tenant isolation. After the
  first independent review, removed `tenant/RLS work` from the production
  persistence gate: passing `saas-evidence` cannot authorize rejected tenancy
  work. The gate now covers customer-data onboarding and production persistence.
- Backlog lines 1-47: marked original tasks, estimates, sequence, and exit gate
  as a historical rejected proposal, while adding a current performance
  carry-forward section. It points to C1/C2/C3 and C8 dispositions in the
  canonical register and T13 for the page-load budget probe. The original
  P0-00 task list stays as historical context.
- Backlog lines 149, 218-222, 462-467: explicitly marked P0-00's formulation
  historical, removed the false statement that an implemented probe gates
  production, ended its dependency on rejected tenancy packages, and replaced
  the obsolete instruction to update this ledger with a pointer to the current
  register and ADR-001.

## Verification

- `python scripts/check_docs_hq_links.py`: exit 0,
  `Documentation HQ link check passed (91 markdown files scanned).`
- Direct relative-link scan of the two owned files: exit 0,
  `Direct relative link scan passed (18 links in 2 files).`
- `git diff --check -- docs/architecture/ENTERPRISE_SAAS_ROADMAP.md docs/architecture/ARCHITECTURE_BACKLOG.md`:
  exit 0, no output.
- Direct full-file whitespace scan of both owned files: exit 0,
  `Direct whitespace scan passed (2 files; 24 intentional Markdown hard breaks preserved).`
  Those hard breaks are exactly two terminal spaces in the pre-existing
  historical Markdown; no other trailing whitespace remains.
- `git diff --stat --` the two owned files: 2 files changed, 62 insertions,
  36 deletions. `git status --short --` the same paths showed both modified.

No behavioral tests were run for this prose-only packet. External provider,
owner, deployment, and performance probe evidence remains open in the canonical
register. Scoped independent re-review of the gate correction is the next step.
