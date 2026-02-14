# Performance

Documentation HQ: [README](README.md)

Date: 2026-02-14

## Baseline Method

Hot-path benchmarks are run with:

```bash
python streamlit_app/scripts/perf_hotpaths.py
```

Benchmark dataset (synthetic but representative):
- 8 users
- 5 goals/user
- 3 objectives/goal
- 4 KRs/objective
- 6 tasks/KR

Metrics captured:
- median latency (ms)
- median SQL query count per call

## Phase 1 Findings

Top 3 user-visible slowness sources:
1. `get_leadership_metrics` loaded nested ORM graph and performed heavy Python traversal.
2. `get_hours_by_goal` loaded full hierarchy + all work logs, then filtered in Python.
3. `get_krs_needing_checkin` eagerly loaded KR tasks that were not needed.

Top 3 developer pain sources:
1. Missing CI quality gate for lint/type/test enforcement.
2. Large monolithic files (`crud.py`, `components.py`, `dialogs.py`) increase change risk.
3. Duplicate dialog function definitions in `streamlit_app/src/ui/dialogs.py` complicate maintenance.

## Before/After Results

| Hot path | Before median ms | After median ms | Improvement | Before queries | After queries |
| --- | ---: | ---: | ---: | ---: | ---: |
| `get_leadership_metrics` | 87.20 | 31.60 | 63.8% faster | 6 | 4 |
| `get_krs_needing_checkin` | 10.55 | 2.78 | 73.6% faster | 3 | 2 |
| `get_hours_by_goal` | 24.01 | 1.26 | 94.8% faster | 5 | 1 |

After values are from current code using `streamlit_app/scripts/perf_hotpaths.py`.

## What Changed

1. `get_leadership_metrics`:
- Replaced nested relationship hydration with flatter SQL queries for task and KR data.
- Preserved output payload shape while reducing query count and object churn.

2. `get_krs_needing_checkin`:
- Removed unnecessary eager loading of `KeyResult.tasks`.

3. `get_hours_by_goal`:
- Replaced Python tree traversal with SQL aggregation using outer joins and date-windowed sum.

4. Deadline scoring correctness/performance:
- `streamlit_app/utils/deadline_utils.py` now accepts both dict and ORM-style inputs.
- Removed exception-heavy execution paths in dashboard/report flows that previously masked deadline states.

## Budgets and Regression Guards

Enforced by `test_performance_hotpaths.py`:
- `get_leadership_metrics`: <= 4 queries
- `get_krs_needing_checkin`: <= 2 queries
- `get_hours_by_goal`: <= 1 query

Run all tests:

```bash
python -m pytest -q
```

Current result:
- `45 passed in 48.21s`
