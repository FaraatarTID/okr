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

## Check-In Snapshot RPC (Supabase API Mode)

The consolidated `ritual.snapshot` read kind (`fn_ritual_snapshot` RPC, migration `y2d3e4f5a6b7`) replaces the per-section fan-out for the Check-In page in Supabase API mode:

- Warm RPC round trip: ~0.65-0.72 s (vs ~1.9 s for the legacy concurrent fan-out over the free-tier pooler).
- Single SQL execution returns key results, weekly plan, retrospectives, work logs, and experiments.
- Fallback to the legacy fan-out occurs only on missing-function errors (SQLSTATE 42883); all other failures propagate fail-closed.
