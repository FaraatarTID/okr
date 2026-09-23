# T03 — Actor-presence audit

## Objective

Audit the seven F2 read kinds from the browser/BFF boundary through the
backend and `get_node`; prove that a verified actor reaches every protected
read or make an absent actor fail closed end to end.

## Required surface

The canonical register F2 row names these seven kinds:

1. `node.get`
2. `node.detect_type`
3. `work_logs.by_task`
4. `experiments.for_kr`
5. `experiments.active_for_kr`
6. `alignments.context`
7. `mindmap.root`

Inspect BFF route policy/actor-required behavior, backend auth/scope resolution,
and `get_node` call sites. Build a matrix for all seven: public request entry,
auth/actor contract at each hop, downstream resolver, existing tests, and any
gap. A source-string-only test is not proof that the request path refuses an
actorless request.

## Owned scope

Inspect and, only where needed, edit the relevant route policy, BFF/backend
boundary, `src/crud_query_helpers.py`, and focused tests for these seven kinds.
Before changes, reserve exact files in your report and avoid unrelated route,
authorization, or read-path refactors. Do not decide or change P0-2 task
visibility; that is T02 and awaits the product decision. Serialize any shared
read-path edit with T02/T32.

If a backend API route or auth contract changes, coordinate the single shared
contract lane exactly as required by the execution plan (OpenAPI export, both
client generation commands, route-policy/allowlist generation, generated
artifact and mutation-auth-matrix checks). Do not hand-edit generated artifacts.

## Acceptance

- Every listed read kind is proven to reject an actorless request end to end, or
  the boundary is hardened with behavioral tests that demonstrate refusal
  before protected data is returned.
- Positive authenticated controls show each read is still reachable for an
  authorized actor; no vacuous reject-all result passes.
- Record all seven paths, exact files, focused commands/results, and any
  remaining external/owner gate in `task-T03-report.md`.
- Preserve existing user changes; do not edit the shared progress ledger.
- No Git writes: `.git` is read-only here.

## Workflow

Use one implementer and an independent reviewer. Stop and report if the source
contract is ambiguous or if proving a route requires making a P0-2 visibility
decision. Do not claim T03 complete before independent review.
