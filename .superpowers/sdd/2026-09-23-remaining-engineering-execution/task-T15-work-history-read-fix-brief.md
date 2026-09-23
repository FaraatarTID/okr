# T15 follow-up — Work History read API defect

Status: narrowly authorized backend support fix for the required rendered Inspector work-history/RTL acceptance.

## Root cause

The real `work_logs.by_task` endpoint fails before serialization at `backend_app/read_query_helpers.py:910`: `getattr(row, "start_time", main.datetime.min)` eagerly evaluates its default expression, but `backend_app.main` has no `datetime` attribute. A direct reproduction against the isolated T15 SQLite database raised `AttributeError` despite the persisted `WorkLog.start_time` being present. The browser shows `Loading work history...` while the request retry helper retries 5xx responses.

## Owned files

- Production: only `backend_app/read_query_helpers.py`, replace the invalid fallback with a safe local `datetime.min` or sort by the required `WorkLog.start_time` field.
- Regression coverage: new focused `tests/test_work_log_history_read.py` using an authenticated real `/v1/read/query` request and persisted work logs.
- Update the T15 report and coordinator progress ledger with reproduction and verification.

Do not change SPA behavior, work-log authorization, data schemas, task visibility, OpenAPI, or other read kinds. T02's owned files do not overlap this fix. Complete before T32 owns the read-budget slice.

## Required TDD and acceptance

1. Create an authorized user and task tree plus two persisted completed WorkLog rows with distinct `start_time` values.
2. Call the real HTTP endpoint with `kind="work_logs.by_task"`; before the fix, observe the controlled HTTP 500/error caused by the missing `main.datetime` access.
3. Apply the smallest correction. Assert HTTP 200, both IDs/summaries, and descending start-time order.
4. Run the regression, neighboring read-query tests, Ruff/py_compile, and the complete opted-in T15 browser suite. Capture the exact `work_logs.by_task` response path and verify the rendered RTL summary.
