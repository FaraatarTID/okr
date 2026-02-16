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

## Regression Guard Tests

- `tests/test_performance_hotpaths.py`
- `tests/test_deadline_utils.py`
- `tests/test_atlas_cache_performance.py`

Run locally:

```bash
python streamlit_app/scripts/perf_hotpaths.py
python streamlit_app/scripts/perf_atlas_rerun.py
python -m pytest -q tests/test_performance_hotpaths.py
```
