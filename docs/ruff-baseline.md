# Ruff baseline: blind excepts and bandit findings

Documentation HQ: [README](../README.md)

Status: `IN FORCE` from 2026-09-29. This is a ratchet, not a clean-up: existing findings are recorded, not judged.

## What is enabled

`pyproject.toml` adds `BLE` (blind `except`) and `S` (bandit) to ruff's defaults (E4, E7, E9, F). The CI step still runs
`ruff check ... --select E9,F63,F7,F82` and does not read this configuration, so the CI gate for these rules is
[tests/test_ruff_baseline.py](../tests/test_ruff_baseline.py), which runs in the pytest job.

- `tests/**` ignores `S`: asserts, throwaway literals and subprocess calls are the point of a test. `BLE` still applies to tests.
- Everything else is checked in full, except the files listed below.

## The baseline

170 findings in 65 files: 101 `BLE001` and 69 `S` findings (`S101`, `S104`, `S105`, `S106`, `S108`, `S110`, `S112`,
`S310`, `S506`, `S603`, `S607`). The first version of this page said 200 findings, 125 and 75; the committed baseline
file said 200, 126 and 74, so that text was slightly off, and it has been recomputed from the file. Reviewed and
removed on 2026-09-30: 20 findings in `backend_app/worker.py`, `backend_app/security_state.py` and `src/database.py`, then
10 more in `src/audit.py`, `src/services/ai_provider.py` and `src/services/supabase_api_mode_transport.py` (see "What has been reviewed").

Two records describe the same thing and must agree: the per-file list in `[tool.ruff.lint.per-file-ignores]` and the
per-file counts in [tests/ruff_baseline.json](../tests/ruff_baseline.json). The test fails if they differ.

A per-file ignore hides **every** finding of that rule in the file, old or new. So the test re-runs ruff with `--isolated`
(no per-file ignores) and compares real counts with the baseline:

| Situation | Result |
|---|---|
| A new finding in a listed file, or in any file | Fails: fix it, or add `# noqa: <code> - <reason>` |
| A finding was fixed and the baseline was not lowered | Fails: lower the count and remove the file's line when it reaches zero |
| `pyproject.toml` and the JSON disagree | Fails |

The counts only move down. Never raise a count to make the test pass.

## What this does and does not claim

- **The baseline is not an approval.** 87 of the remaining 101 blind excepts are outside tests (it was 112 before the reviews below). Apart from the files under What has been reviewed, they were listed, not reviewed.
  Many are visibly fail-closed or best-effort by design (a failed `logger.debug` on shutdown, `return None` after a parse
  failure); some may hide a real error. Nobody has classified them.
- **They were not annotated.** A reason on each `noqa` has to come from someone who has read the handler. Writing 101 reasons
  in bulk from the file names would produce text that looks reviewed and is not. The way to reduce the count is: when you touch
  a handler, either narrow the exception or add `# noqa: BLE001 - <why swallowing is right>`, then lower the baseline.
- `S603`/`S607` in `scripts/` are subprocess calls with fixed argument lists, `S310` is `urllib` against configured URLs,
  `S105`/`S106` outside tests are named constants (for example a config key name), not credentials. This is from reading the
  rule names and sampling, not from reviewing each one.
- S608 (SQL built from strings): all four sites were read and are annotated in place with the reason, so none is in the baseline any more. See below.

## What has been reviewed

Reviewed 2026-09-30, by reading each handler and its callers: `backend_app/worker.py` (9 `BLE001`),
`backend_app/security_state.py` (6 `BLE001`, 1 `S110`, 3 `S608`) and `src/database.py` (1 `S608`). Each is now either
narrowed or carries a `# noqa: <code> - <reason>` that says what the swallow does. Tests pin that behaviour in
[tests/test_blind_except_contracts.py](../tests/test_blind_except_contracts.py) (14 tests; 9 of 9 mutations of the handlers killed).

| Where | Decision |
|---|---|
| `worker.py` job thread `except BaseException` | Kept. The exception is stored and re-raised in the calling thread, so `SystemExit` is not lost with the thread. |
| `worker.py` claim, status write, job execution, finalization, prune, reap, queue depth, loop guard | Kept. Each is logged (with traceback, or as a warning for the advisory queue-depth gauge) and the worker continues. Housekeeping retries at the next interval. |
| `security_state.py` two JSON fallbacks | **Narrowed** from `Exception` to `ValueError`. `json.loads` raises only `ValueError` for bad text, so nothing that was caught before is missed, and an unrelated bug is no longer swallowed. |
| `security_state.py` Redis load/store/dispose | Kept. `redis` is an optional dependency, so its error types cannot be named here. A failed load returns `None`, which the caller turns into `409`; it never replays a wrong response (tested). |
| `security_state.py` `dispose` (database) | Kept, best-effort shutdown. |
| Four `S608` sites | Kept, annotated. Only module-built fragments (`key_clause`, `lock_clause`, a fixed tuple of table names, quoted table metadata) are spliced into the SQL; every value is a bound parameter. This is from reading the four call sites and their inputs, not a security audit. |

Second batch, reviewed 2026-09-30 (10 `BLE001`), tests in
[tests/test_blind_except_batch2_contracts.py](../tests/test_blind_except_batch2_contracts.py) (38 tests; 12 of 12 mutations killed):

| Where | Decision |
|---|---|
| `supabase_api_mode_transport.py` `_as_int`, `_parse_dt`, the two Atlas snapshot parsers | **Narrowed** to the exceptions the call can raise (`TypeError`, `ValueError`, `OverflowError`; `RecursionError` for stored JSON). `int(float("inf"))` raises `OverflowError`, which a narrower `(TypeError, ValueError)` would have let escape; a test fixes that. |
| `supabase_api_mode_transport.py` HTTP client close | Kept, annotated: best-effort cleanup, logged, and the client is dropped either way. |
| `ai_provider.py` `response.json()` | **Narrowed** to `ValueError` (`requests`' decode error subclasses it). A test shows an `AttributeError` now surfaces instead of becoming an error value. |
| `ai_provider.py` Gemini and OpenAI-compatible calls | Kept, annotated: the SDKs raise arbitrary types, and the failure is returned as redacted error text (see #210 in the plan). |
| `audit.py` database sink | Kept, annotated; it already logged. |
| `audit.py` actor lookup | Kept, annotated, and **no longer silent**: it returned empty identity with no log at all. It now warns once per process and keeps the traceback at debug. An audit event still gets written without an actor rather than failing. |

What this does **not** claim: the other 101 blind excepts and 69 `S` findings have not been reviewed. The question this
page used to leave open, whether stored job error text can carry sensitive data, was answered: it could, through a URL
in a library exception, and it is fixed and tested (`redact_error_text`, see
[REMAINING_ENGINEERING_PLAN.md](REMAINING_ENGINEERING_PLAN.md)).

## How to lower it

Fix or annotate the finding, then lower its count for that file in **both** `tests/ruff_baseline.json` and the matching
`[tool.ruff.lint.per-file-ignores]` line in `pyproject.toml` (drop the code from the list, or the whole line when nothing is
left). There is no generator on purpose: the edit is small and the test names any mismatch.