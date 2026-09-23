Documentation HQ: [README](../../../README.md)

# T08 implementation report — backend app mypy slice

## Scope and change

- `backend_app/main.py`: aligned four dormant compatibility wrappers for idempotency with the existing `main_runtime_helpers` keyword and return contracts. The old wrappers passed nonexistent `session`, `scope_id`, and `status_code` parameters and claimed a tuple return where the implementation returns a replay payload or `None`.
- `backend_app/observability_http.py`: snapshot the request's data-access context once at each metrics recording point, then read optional fields from the narrowed value. This preserves the recorded values and avoids repeated context lookups.
- No tests, shared helper files, generated files, or quality gate policy were edited.

## Static evidence

- Baseline full command: `.venv\Scripts\mypy.exe --no-incremental --ignore-missing-imports --follow-imports=skip backend_app src scripts tests` found **160 errors in 31 files**. Assigned files accounted for **12**: six in `main.py`, six in `observability_http.py`.
- After change, the same full command found **135 errors in 28 files** with **zero** assigned-file errors (exit 1 for remaining repository debt). Other agents are editing disjoint mypy slices concurrently, so the repository total delta is not attributable solely to T08.
- The two-file invocation of the same mypy flags reports zero both before and after because `--follow-imports=skip` erases the helper types unless the imported backend modules are also command targets. The full-scope command is the meaningful acceptance measurement.

## Runtime checks

- `.venv\Scripts\pytest.exe -q tests/test_backend_observability.py tests/test_backend_error_envelope.py tests/test_backend_mutation_api.py`: **131 passed**, two environment warnings (Starlette/httpx deprecation, pytest cache write permission).
- `.venv\Scripts\ruff.exe check backend_app/main.py backend_app/observability_http.py`: **All checks passed**.

## Review notes

- The `main.py` wrappers currently have no direct repository call site; mutation/workflow handlers call the runtime helpers directly. The wrappers now delegate with the helper's actual contract. Independent review should check this seam against future direct callers.
- A scoped diff snapshot is `task-T08-review.diff`.
