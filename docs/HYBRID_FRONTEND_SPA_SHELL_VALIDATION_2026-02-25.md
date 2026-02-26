Documentation HQ: [README](../README.md)

Hybrid Frontend SPA Shell Validation

Date
- 2026-02-25

Backlog mapping
- Work item: `HFM-030`

Source record
- Machine-readable validation: [HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.json](HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.json)

## 1. Acceptance Scope

Validate that SPA shell provides:
1. Base navigation controls.
2. Cycle selector and scope selector.
3. Role-aware entrypoints via rollout policy.

## 2. Verified Controls

- `cycle-id` input for cycle selection.
- `owner-ids` input for owner scope filtering.
- `mode` select for navigation mode.
- `lens` select for view context.

## 3. Verified Sections

- Focus Map section is rendered.
- Inspector section is rendered.
- Streamlit report bridge handoff section is rendered.

## 4. Role-Aware Entry Validation

- Rollout config route consumes environment policy keys:
  - `OKR_SPA_ROLLOUT_USERNAMES`
  - `OKR_SPA_ROLLOUT_ROLES`
  - `OKR_SPA_ROLLOUT_TEAM_IDS`
  - `OKR_SPA_ROLLOUT_ALLOW_ALL`
  - `OKR_SPA_ROLLOUT_ALLOW_PREVIEW_BYPASS`
- Rollout evaluator supports cohort decisions by username/role/team and allow-all/preview bypass paths.
- Shell renders rollout status messaging to expose access decisions to the user.

Exit
- `HFM-030` acceptance criteria are met for shell/navigation capabilities.
