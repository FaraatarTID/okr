# Performance Baselines

Documentation HQ: [README](README.md)

This document tracks performance baselines and query-budget guardrails for critical hot paths.

## Benchmark Method

- Script: `streamlit_app/scripts/perf_hotpaths.py`
- Environment: local benchmark run (representative developer machine)
- Purpose: detect regressions in latency and SQL query count for critical analytics paths

## Current Baselines (Measured February 16, 2026)

| Path | Median Time | P95 Time | Observed Queries | Query Budget |
| --- | --- | --- | --- | --- |
| `get_leadership_metrics` | 10.09 ms | 10.21 ms | 3 | 4 queries |
| `get_krs_needing_checkin` | 1.17 ms | 1.18 ms | 1 | 2 queries |
| `get_hours_by_goal` | 0.77 ms | 0.78 ms | 1 | 1 query |

## Atlas Workspace Rerun Baselines (Measured February 16, 2026)

- Script: `streamlit_app/scripts/perf_atlas_rerun.py`
- Scope: Atlas data rerun path (`render_level -> render_atlas_workspace` snapshot/index/nav prep)

Before Atlas optimization:

| Scenario | Median Total | Snapshot | Render From Snapshot | Breadcrumb | Queries | Payload |
| --- | --- | --- | --- | --- | --- | --- |
| Cache miss | 18.074 ms | 13.283 ms | 4.232 ms | 3.371 ms | 9 | 72,097 bytes |
| Cache hit | 3.217 ms | 0.293 ms | 2.343 ms | 1.448 ms | 4 | 72,097 bytes |

After Atlas optimization:

| Scenario | Median Total | Snapshot | Render From Snapshot | Breadcrumb | Queries | Payload |
| --- | --- | --- | --- | --- | --- | --- |
| Cache miss | 8.711 ms | 7.274 ms | 0.912 ms | 0.012 ms | 5 | 61,877 bytes |
| Cache hit | 1.674 ms | 0.245 ms | 0.912 ms | 0.006 ms | 0 | 61,877 bytes |

## Atlas App-Shell Rerun Baselines (Measured February 16, 2026)

- Script: `streamlit_app/scripts/perf_app_rerun.py`
- Scope: non-Atlas rerun work around `render_level -> render_atlas_workspace` in `streamlit_app/app.py`

Before app-shell cache optimization (baseline behavior):

| Scenario | Median Total | P95 Total | Median Queries | P95 Queries |
| --- | --- | --- | --- | --- |
| Cache miss | 201.085 ms | 201.085 ms | 5 | 5 |
| Cache hit | 198.266 ms | 203.632 ms | 4 | 4 |

After app-shell cache + admin-warning fast-path optimization:

| Scenario | Median Total | P95 Total | Median Queries | P95 Queries |
| --- | --- | --- | --- | --- |
| Cache miss | 1.589 ms | 1.589 ms | 3 | 3 |
| Cache hit | 0.123 ms | 0.146 ms | 0 | 0 |

## Login Page Bootstrap Baselines (Measured February 16, 2026)

- Script: `streamlit_app/scripts/perf_login_bootstrap.py`
- Scope: login page open path and submit bootstrap path

Before login-open optimization (old session-open behavior):

| Scenario | Median Time | P95 Time | Median Queries | P95 Queries |
| --- | --- | --- | --- | --- |
| Login open (cold process) | 846.284 ms | 846.284 ms | 2 | 2 |
| Login open (warm process) | 194.594 ms | 195.343 ms | 2 | 2 |

After login-open + async prewarm optimization:

| Scenario | Median Time | P95 Time | Median Queries | P95 Queries |
| --- | --- | --- | --- | --- |
| Login open | 0.001 ms | 0.008 ms | 0 | 0 |
| Login submit (first without prewarm completion) | 194.453 ms | 194.453 ms | 2 | 2 |
| Login submit (after prewarm completion) | 0.003 ms | 0.004 ms | 0 | 0 |
| Login submit (cached in process window) | 0.001 ms | 0.001 ms | 0 | 0 |

## Regression Guard Tests

- `tests/test_performance_hotpaths.py`
- `tests/test_deadline_utils.py`
- `tests/test_atlas_cache_performance.py`
- `tests/test_app_rerun_cache_performance.py`
- `tests/test_startup_bootstrap.py`

Run locally:

```bash
python streamlit_app/scripts/perf_hotpaths.py
python streamlit_app/scripts/perf_atlas_rerun.py
python streamlit_app/scripts/perf_app_rerun.py
python streamlit_app/scripts/perf_login_bootstrap.py
python -m pytest -q tests/test_performance_hotpaths.py
```
