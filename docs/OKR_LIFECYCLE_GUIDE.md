# OKR Lifecycle Guide
Documentation HQ: [README](../README.md)

This guide reflects the lifecycle logic currently implemented in `streamlit_app/src/models.py`, `streamlit_app/src/domain/lifecycle.py`, and `streamlit_app/src/crud.py`.

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
