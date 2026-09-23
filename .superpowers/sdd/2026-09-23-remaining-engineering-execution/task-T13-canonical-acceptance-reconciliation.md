# T13 canonical C3 acceptance reconciliation

## Finding

The authoritative register's C3 row said a page-load budget probe should run
and fail on material elapsed-time regression in CI. The approved execution
plan's T13 table and detailed design instead specify deterministic PR checks
(request ordering, parallelism, de-duplication, no warm-cache refetch) and a
pinned-condition warmed-stack browser budget probe in release evidence. It
explicitly excludes noisy wall-clock thresholds from PR CI. The row's evidence
also claimed there was no performance probe in scripts/tests, although the
existing offline trace analyzer and its tests do exist and do not measure a
browser waterfall or set a target.

## Correction

Updated only C3's evidence, deliverable, and acceptance in
`docs/REMAINING_ENGINEERING_PLAN.md` to match the approved execution plan. The
row now distinguishes deterministic PR request contracts from warmed browser
release evidence, and keeps C3 open until an approved successful warmed-stack
artifact exists. No implementation or closure status is claimed.

## Basis

- `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md` T13
  table and the detailed performance design at the C3 section.
- `docs/architecture/performance.md` existing trace analyzer contract states
  that it accepts supplied spans and does not infer or assert a target.
- Read-only T13 reconnaissance confirmed `scripts/diagnose_page_load.py` and
  `tests/test_page_load_diagnostics.py` are offline trace tooling rather than a
  browser waterfall or warmed-stack budget probe.

## Scope

Only the C3 register row and this report were changed. T13 implementation
remains ordered after the T11/T12/T15 frontend behavior settles. No PR CI
workflow, probe, release evidence artifact, or performance claim was changed.
