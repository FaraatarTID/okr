# Performance Baselines

Documentation HQ: [README](README.md)

This document tracks performance baselines and query-budget guardrails for critical hot paths.

## Current Baselines (Measured February 16, 2026)

| Path | Median Time | P95 Time | Observed Queries | Query Budget |
| --- | --- | --- | --- | --- |
| `get_leadership_metrics` | 10.09 ms | 10.21 ms | 3 | 4 queries |
| `get_krs_needing_checkin` | 1.17 ms | 1.18 ms | 1 | 2 queries |
| `get_hours_by_goal` | 0.77 ms | 0.78 ms | 1 | 1 query |

## Regression Guard Tests

- `tests/test_performance_hotpaths.py`
- `tests/test_deadline_utils.py`
- `tests/test_startup_bootstrap.py`

Run locally:

```bash
python -m pytest -q tests/test_performance_hotpaths.py
```
