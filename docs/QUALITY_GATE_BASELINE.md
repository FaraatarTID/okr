Documentation HQ: [README](../README.md)

Quality Gate Baseline (Time-Boxed)

Date
- 2026-02-24
- Reviewed 2026-09-20

Purpose
- Make temporary quality-gate exceptions explicit, owned, and time-boxed.
- Support staged expansion of lint/type coverage without silent long-term drift.

Active Baseline Items

| ID | Scope | Rationale | Expires On |
| --- | --- | --- | --- |
| QG-002 | Repo-wide mypy remains staged; broad default coverage is active for `scripts` and the runtime-core `backend_app` modules. Measured 2026-09-20: 127 errors in 24 of 347 checked files (`src` 10, `tests` 10, `backend_app` 2, `scripts` 2), led by `arg-type` 56, `union-attr` 16, and `attr-defined` 15. | Type debt is retired incrementally while keeping CI stable. This is now the only remaining exception; it is re-dated to a nearer review point with a staged burn-down rather than extended by a year. | 2026-11-15 |

Closed Baseline Items

| ID | Scope | Closed On | How it was closed |
| --- | --- | --- | --- |
| QG-001 | Repo-wide Ruff format check was targeted at two files. | 2026-09-20 | Expanded to repo scope: `ruff format --check .` now covers 348 files and passes. `alembic/versions` is excluded because applied migrations are immutable; that is the only path carve-out in the gate. Enforced in CI (`Format Check (Ruff, repo-wide)`) and in the `ruff-format-check-repo` pre-commit hook. |

QG-002 burn-down plan
- 2026-10-15: at most 80 errors.
- 2026-11-15: at most 40 errors.
- 2026-12-31: zero errors, and the item is removed.
- Re-measure with `python -m mypy --no-incremental --ignore-missing-imports --follow-imports=skip backend_app src scripts tests`.

Enforcement
- CI and pre-commit run `python scripts/check_quality_gate_baseline.py`.
- If any baseline item is past `Expires On`, the gate fails.

Next Milestone
- By 2026-11-15, either:
  - Retire QG-002 by upgrading the mypy gate to full repo scope, or
  - Replace it with a newly reviewed item and an updated expiry date.
