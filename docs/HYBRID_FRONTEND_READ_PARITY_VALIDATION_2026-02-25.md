Documentation HQ: [README](../README.md)

Hybrid Frontend Read Parity Validation

Date
- 2026-02-25

Backlog mapping
- Work item: `HFM-031`

Source record
- Machine-readable validation: [HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.json](HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.json)
- Fixture source: [fixtures/hybrid_frontend/atlas_snapshot.response.json](fixtures/hybrid_frontend/atlas_snapshot.response.json)

## 1. Acceptance Scope

Validate read parity for pilot datasets:
1. Focus Map hierarchy render parity.
2. Inspector read-field parity.

## 2. Pilot Fixture Coverage

Validated pilot fixture hierarchy:
- Goals: `1`
- Objectives: `1`
- Key Results: `1`
- Tasks: `2`

## 3. Field Parity Coverage

Validated field sets used by SPA read surfaces:
- Goal: `id`, `title`, `description`, `progress`, `owner_id`
- Objective: `id`, `title`, `description`, `progress`, `score_mode`, `weight`
- Key Result: `metric_type`, `start_value`, `current_value`, `target_value`, `unit`
- Task: `status`, `deadline`, `timer_started_at`, `total_time_spent`, `assignee_id`

## 4. Render Signals

- Focus Map section is present in SPA shell.
- Inspector section is present in SPA shell.
- Inspector fields include owner/path and key KR/task detail rows needed for parity checks.

Exit
- `HFM-031` acceptance criteria are met for read-only Focus Map and Inspector parity using pilot fixture datasets.
