# T05 — Roadmap and backlog truth

## Objective

Reconcile the enterprise roadmap and superseded architecture backlog with the
authoritative remaining-work register, while preserving ADR-001 and current
Documentation HQ navigation.

## Sources of truth and evidence

- `docs/REMAINING_ENGINEERING_PLAN.md` is authoritative for current open work.
- `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md` has a stale remaining-work
  description (register B2).
- `docs/architecture/ARCHITECTURE_BACKLOG.md` is superseded, but still contains
  an active performance-probe claim and historical tenancy execution text
  (register B4).
- Preserve `docs/architecture/ADR-001-single-tenant.md` and links to the current
  register; do not revive tenant IDs, shared-database RLS, or rejected tenancy
  scope.

## Owned files

- `docs/architecture/ENTERPRISE_SAAS_ROADMAP.md`
- `docs/architecture/ARCHITECTURE_BACKLOG.md`

Do not edit the canonical register, README, lifecycle policy/registry, code,
tests, workflows, or unrelated architecture docs. If a needed correction falls
outside these files, report it for coordinator disposition.

## Acceptance

- Roadmap text distinguishes repository implementation from owner/provider/
  deployment evidence still required and links to the canonical register.
- Backlog text clearly marks superseded work as historical; the old active
  performance-probe claim is removed or points to the current authoritative
  budget task; rejected tenancy text is clearly historical and cannot be read
  as scheduled implementation.
- ADR-001's single-tenant decision is preserved; no tenant identifiers or
  shared-database RLS are reintroduced.
- Documentation HQ link check passes; direct link and whitespace scans for
  both owned files pass. No behavioral tests are needed for this prose-only
  packet.
- Report exact files/hunks, checks and outputs; do not claim external facts.

## Workflow

Use a dedicated implementer and an independent reviewer. Preserve all existing
user changes. The managed `.git` directory is read-only: do not attempt branch,
worktree, index, or commit writes. Stop and report if the acceptance requires
facts or changes beyond the owned files.
