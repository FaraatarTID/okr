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

200 findings in 70 files at the time of writing: 125 `BLE001` and 75 `S` findings (`S104`, `S105`, `S106`, `S108`,
`S110`, `S112`, `S310`, `S506`, `S603`, `S607`, `S608`). `S101` (assert) is never counted because it is a test-only pattern and
is ignored there.

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

- **The baseline is not an approval.** ~111 of the 125 blind excepts are outside tests. They were listed, not reviewed.
  Many are visibly fail-closed or best-effort by design (a failed `logger.debug` on shutdown, `return None` after a parse
  failure); some may hide a real error. Nobody has classified them.
- **They were not annotated.** A reason on each `noqa` has to come from someone who has read the handler. Writing 111 reasons
  in bulk from the file names would produce text that looks reviewed and is not. The way to reduce the count is: when you touch
  a handler, either narrow the exception or add `# noqa: BLE001 - <why swallowing is right>`, then lower the baseline.
- `S603`/`S607` in `scripts/` are subprocess calls with fixed argument lists, `S310` is `urllib` against configured URLs,
  `S105`/`S106` outside tests are named constants (for example a config key name), not credentials. This is from reading the
  rule names and sampling, not from reviewing each one.
- `S608` (SQL built from strings) appears four times: three in `backend_app/security_state.py` and one in `src/database.py`. Two of them were read while writing this: `security_state.py:448` splices only the internal fragments `key_clause` and `lock_clause` into the statement and binds the values, and `database.py:650` interpolates table and column names taken from the model metadata, quoted with `"`, into a `MAX()` query. Neither takes caller input on the path read, which is a reading of two call sites, not a review. The other two (`security_state.py:483` and `:739`) were not read. Read those first.

## How to lower it

Fix or annotate the finding, then lower its count for that file in **both** `tests/ruff_baseline.json` and the matching
`[tool.ruff.lint.per-file-ignores]` line in `pyproject.toml` (drop the code from the list, or the whole line when nothing is
left). There is no generator on purpose: the edit is small and the test names any mismatch.