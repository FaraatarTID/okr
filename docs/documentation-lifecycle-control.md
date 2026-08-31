# Documentation Consolidation and Lifecycle Control

Back to [Documentation HQ](README.md).

Status: `IN-PROGRESS` for P0-05.

This document defines how the architecture backlog, delivery system, status ledger, worklog, and decision records stay synchronized. It is the working control contract for architecture documentation during the pre-SaaS transition.

## Documentation HQ

[README.md](README.md) is the navigation hub for architecture and delivery documentation. The hub should point readers to the current source of truth instead of duplicating decisions across independent notes.

| Artifact | Role | Update rule | Owner candidate |
|---|---|---|---|
| [PRE_SAAS_ARCHITECTURE_BACKLOG.md](../PRE_SAAS_ARCHITECTURE_BACKLOG.md) | Work package scope and sequencing | Update lifecycle status and evidence link when a package changes state | Architecture |
| [ARCHITECTURE_DELIVERY_SYSTEM.md](ARCHITECTURE_DELIVERY_SYSTEM.md) | Delivery process and verification model | Change only when the operating model changes | Architecture and delivery |
| [architecture-status.md](architecture-status.md) | Current status ledger | Keep synchronized with the backlog snapshot | Architecture |
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

- Documentation HQ link check passed: `python scripts/check_docs_hq_links.py` scanned 62 Markdown files.
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

P0-05 should move to `VERIFIED` only after the navigation and link evidence is attached to the status ledger.
