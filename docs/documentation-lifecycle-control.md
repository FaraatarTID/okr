# Documentation Consolidation and Lifecycle Control

Documentation HQ: [README](../README.md)

Status: `HISTORICAL` — the P0-05 control pass this document records is closed
(`VERIFIED` in the status ledger on 2026-09-01). It is retained as the
implementation and history record of that pass, not as a live contract.

The **policy reference** for lifecycle categories and the current registry is
[DOCUMENTATION_LIFECYCLE.md](DOCUMENTATION_LIFECYCLE.md); this document records
how that policy was established and what it changed.

This document defined how the architecture backlog, delivery system, status ledger, worklog, and decision records stay synchronized. It was the working control contract for architecture documentation during the pre-SaaS transition.

## Documentation HQ

[README.md](../README.md) is the navigation hub for architecture and delivery documentation. The hub should point readers to the current source of truth instead of duplicating decisions across independent notes.

| Artifact | Role | Update rule | Owner candidate |
|---|---|---|---|
| [PRE_SAAS_ARCHITECTURE_BACKLOG.md](architecture/PRE_SAAS_ARCHITECTURE_BACKLOG.md) | Work package scope and sequencing (archived historical record) | Frozen; superseded by [REMAINING_ENGINEERING_PLAN.md](REMAINING_ENGINEERING_PLAN.md) | Architecture |
| [ARCHITECTURE_DELIVERY_SYSTEM.md](ARCHITECTURE_DELIVERY_SYSTEM.md) | Delivery process and verification model; describes the process that was used, and the backlog it tracked is superseded | Frozen | Architecture and delivery |
| [architecture-status.md](architecture-status.md) | Status ledger for the pre-SaaS packages (now historical) | Superseded by [REMAINING_ENGINEERING_PLAN.md](REMAINING_ENGINEERING_PLAN.md) for current status | Architecture |
| [WORKLOG.md](WORKLOG.md) | Append-only execution record | Add a dated entry for every material state change | Delivery owner |
| `docs/*-adr.md` | Architecture decision record | Record context, decision, alternatives, and evidence | Decision owner |
| `docs/*-inventory.md` | Evidence and discovery artifact | Mark observed facts separately from proposals | Work package owner |

## Lifecycle synchronization

Every work package follows the delivery lifecycle defined in the delivery system:

```text
PLANNED -> IN-PROGRESS -> IMPLEMENTED -> VERIFIED -> CLOSED
```

The three tracking surfaces have distinct purposes:

- The backlog defines scope, dependencies, and intended verification.
- The status ledger provides the compact current state and evidence pointer.
- The worklog records what changed, when it changed, the next action, and blockers.

A status transition is incomplete until all three surfaces agree. Evidence links must point to a stable repository artifact or a clearly identified command output record.

## Evidence rules

- `IN-PROGRESS` means work has started and an owner or next action is known.
- `IMPLEMENTED` means the planned artifact or code change exists, but verification is not complete.
- `VERIFIED` requires evidence tied to the acceptance criteria, not merely a written proposal.
- `CLOSED` requires the evidence, retro note, and follow-up risks to be recorded.
- Proposals must use language such as `candidate`, `working decision`, or `proposed` until verified.
- A documentation artifact must not claim that a test, check, deployment, or rehearsal passed unless its output is recorded.

## Ownership and review

Each package has one accountable owner, even when several teams contribute. The owner is responsible for:

- keeping the status ledger current;
- attaching verification evidence;
- resolving contradictions between documents;
- recording retro notes and follow-up work;
- marking the package closed only when no required acceptance work remains.

Cross-cutting decisions should link back to the affected work package and must not silently override the backlog sequencing.

## Link and navigation policy

- New architecture documents link back to Documentation HQ.
- Relative links are preferred inside the repository.
- The status ledger links to the primary evidence artifact for each active package.
- Duplicate statements should be replaced by a link to the source artifact where practical.
- Broken links are treated as delivery defects for P0-05.

## Current control gaps

- Documentation HQ link check passed: `python scripts/check_docs_hq_links.py` scanned 93 Markdown files (2026-09-14).
- Several package rows still need implementation and verification evidence.
- The initial inventory and boundary proposal contain intentional open questions.
- Existing architecture references need reconciliation against the new status ledger.

## Retro note

The initial control pass exposed that architecture work can accumulate valid documents without a synchronized lifecycle record. The ledger, worklog, and evidence-link rule now make that drift visible; future work should update all three surfaces in the same change.

## Closure evidence for P0-05

- Documentation HQ navigation covers the active architecture artifacts.
- Backlog and status ledger lifecycle values are synchronized.
- Worklog entries exist for material transitions.
- Each active package has an owner candidate, next action, and evidence pointer.
- Repository documentation-link checks pass.
- A short retro note records remaining documentation debt and its owner.

P0-05 moved to `VERIFIED` on 2026-09-01 once the navigation and link evidence was attached to the status ledger. That ledger is now historical; current status lives in [REMAINING_ENGINEERING_PLAN.md](REMAINING_ENGINEERING_PLAN.md).

