# OKR Lifecycle Guide
Documentation HQ: [README](../README.md)

This guide reflects the lifecycle logic currently implemented in `streamlit_app/src/models.py`, `streamlit_app/src/domain/lifecycle.py`, and `streamlit_app/src/crud.py`.

For enterprise rollout sequencing and change-management guidance, see `docs/OKR_ROLLOUT_GUIDE.md`.

## 1. Lifecycle States

Objectives and Key Results use four states:
- `DRAFT`
- `ACTIVE`
- `GRADING`
- `ARCHIVED`

State intent:
- `DRAFT`: planning state; excluded from progress rollups.
- `ACTIVE`: normal execution and tracking state.
- `GRADING`: end-of-cycle review/reflection state.
- `ARCHIVED`: closed historical state (can be re-activated if needed).

## 2. Allowed Transitions

Current transition map:
- `DRAFT -> ACTIVE`
- `ACTIVE -> GRADING` or `ACTIVE -> DRAFT`
- `GRADING -> ARCHIVED` or `GRADING -> ACTIVE`
- `ARCHIVED -> ACTIVE`

Transition validation is enforced in lifecycle logic.

## 3. Key Enforcement Rules

- Objective cannot transition to `ACTIVE` unless it has at least one KR.
- Changing Objective state cascades the same state to child KRs.
- `DRAFT` objectives/KRs are excluded from objective/goal rollups.
- Activation readiness policy should also include BAU boundary screening:
  - routine operating work is released to BAU tracking,
  - only strategic-change KRs move to `ACTIVE`.
  - See `docs/OKR_BAU_BOUNDARY_GUIDE.md`.

## 4. Alignment Graph (Objective-to-Objective)

Beyond Goal->Objective->KR hierarchy, objectives can be linked with alignment edges.

Behavior:
- Links are directional.
- Cycle-creating links are blocked.
- You manage links in Objective Inspector under `Organizational Alignment`.
- Creating/removing links requires mutation authorization on involved objective goals.

## 5. Scoring Modes and Rollups

Objective scoring modes:
- `UNWEIGHTED`: all KRs contribute equally.
- `WEIGHTED`: KR weights affect objective score.

KR score inputs:
- `start_value`, `current_value`, `target_value`, `metric_type`.

Goal rollup:
- derived from objective progress (with objective weights).

## 6. Where to Manage Lifecycle in UI

In Inspector:
- `Lifecycle & Closing`: set state + final reflection.
- Objective inspector: manage alignment links and scoring mode.
- KR inspector: manage KR weight and metric fields.

## 7. Final Reflection Guidance

Use `Final Reflection` on Objective/KR for:
- outcome summary,
- key blockers,
- decisions for next cycle.

This keeps end-of-cycle reasoning auditable for future planning.

## 8. Lifecycle State to Ceremony Mapping

The lifecycle state model should be operated together with the OKR ceremony cadence:

| Lifecycle state | Typical ceremony focus | Expected operating behavior |
|---|---|---|
| `DRAFT` | Planning | Draft Objectives/KRs, align dependencies, confirm metric quality before activation. |
| `ACTIVE` | Weekly check-ins | Execute work, submit KR updates, and resolve blockers transparently. |
| `GRADING` | Review + retrospective | Evaluate final status, capture reflections, and agree on improvements. |
| `ARCHIVED` | Post-cycle learning | Preserve historical outcomes and reactivate only when strategically needed. |

## 9. Rollout Guardrails for New OKR Programs

The following rollout practices are recommended for enterprise adoption (process guidance, not hard-enforced by code):
- Start with a pilot group of roughly 100-250 participants.
- Run at least two full cycles before scaling broadly.
- Schedule weekly check-ins, review, and retrospective dates before cycle kickoff.
- Use retrospective output to define concrete process changes for the next cycle.
- Scale only after evidence shows both adoption quality and outcome quality.
