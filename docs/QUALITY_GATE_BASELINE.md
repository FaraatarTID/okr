Documentation HQ: [README](../README.md)

Quality Gate Baseline (Time-Boxed)

Date
- 2026-02-24

Purpose
- Make temporary quality-gate exceptions explicit, owned, and time-boxed.
- Support staged expansion of lint/type coverage without silent long-term drift.

Active Baseline Items

| ID | Scope | Rationale | Expires On |
| --- | --- | --- | --- |
| QG-001 | Repo-wide Ruff format check is still targeted. | Formatting debt is reduced in planned batches to avoid high-churn refactors in release branches. | 2026-06-30 |
| QG-002 | Repo-wide mypy remains staged; broad default coverage is active for `scripts`, `streamlit_app/src/utils`, and runtime-core modules (`app_entry_helpers`, `session_keys`, selected `backend_app` runtime files). | Type debt is being retired incrementally while keeping CI stable. | 2026-06-30 |

Enforcement
- CI and pre-commit run `python scripts/check_quality_gate_baseline.py`.
- If any baseline item is past `Expires On`, the gate fails.

Next Milestone
- By 2026-06-30, either:
  - Remove the baseline items by upgrading the gates to full repo scope, or
  - Replace them with newly reviewed items and updated expiry dates.
