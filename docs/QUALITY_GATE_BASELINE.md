Documentation HQ: [README](../README.md)

Quality Gate Baseline (Time-Boxed)

Date
- Created 2026-02-24
- Reviewed 2026-09-28

Purpose
- Make temporary quality-gate exceptions explicit, owned, and time-boxed.
- Support staged expansion of lint/type coverage without silent long-term drift.

Active Baseline Items

There are no active baseline exceptions.

Closed Baseline Items

| ID | Scope | Closed On | How it was closed |
| --- | --- | --- | --- |
| QG-001 | Repo-wide Ruff format check was targeted at two files. | 2026-09-20 | Expanded to repo scope: `ruff format --check .` now covers 348 files and passes. `alembic/versions` is excluded because applied migrations are immutable; that is the only path carve-out in the gate. Enforced in CI (`Format Check (Ruff, repo-wide)`) and in the `ruff-format-check-repo` pre-commit hook. |
| QG-002 | Repo-wide mypy was staged; measured 127 errors across 24 of 347 files on 2026-09-20. | 2026-09-28 | CI's `Type Check (Mypy)` runs the complete scope and flags. Final local run: `.venv\\Scripts\\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip backend_app src scripts tests` — `Success: no issues found in 399 source files` (including `tests/test_quality_gate_workflow.py`). That checked-in test parses the workflow with PyYAML `BaseLoader` and asserts the complete command exactly. The earlier 398-file run preceded the addition of that contract test; the 399-file result is the final verified count. |

Enforcement
- CI and pre-commit run `python scripts/check_quality_gate_baseline.py`.
- The generic expiry checker remains active for any future reviewed baseline item; it fails when an item's `Expires On` is before today.

Next Milestone
- No baseline milestone is open. Any future exception must have a documented owner, rationale, and expiry date.
