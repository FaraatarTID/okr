Documentation HQ: [README](../README.md)

Hybrid Frontend Rollback Toggle Contract

Date
- 2026-02-25

Backlog mapping
- Work item: `HFM-001`

Source record
- Machine-readable rollback toggle contract: [HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.json](HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.json)
- Rollback procedure reference: [HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md](HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md)

## 1. Primary Rollback Toggle

- Key: `OKR_SPA_ROLLOUT_ENABLED`
- Rollback value: `false`
- Scope: global
- Effect: disables SPA cohort access and returns users to Streamlit-first fallback flow.

## 2. Scoped Rollback Controls

For targeted rollback without global disable:
- Remove affected entries from `OKR_SPA_ROLLOUT_TEAM_IDS`
- Remove affected entries from `OKR_SPA_ROLLOUT_USERNAMES`
- Adjust `OKR_SPA_ROLLOUT_ROLES` as needed

## 3. Verification Contract

After applying rollback:
1. Restart `spa-web`.
2. Validate `GET /api/rollout` returns `enabled=false` for global rollback or expected scoped cohort exclusion.
3. Confirm cohort behavior matches policy (blocked/allowed) without secret exposure or backend-boundary regression.

## 4. Time Objective

- Rollback completion objective: `<15` minutes.
- Drill evidence reference: [HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.md](HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.md).

Exit
- `HFM-001` acceptance criteria are met with one explicit rollback toggle and operator verification path.
