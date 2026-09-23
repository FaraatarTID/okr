Documentation HQ: [README](../../../README.md)

# T07 follow-up — type the repository readiness workflow test

## Objective and exact ownership

Remove the single `import-untyped` mypy diagnostic introduced by T07's
`tests/test_repository_readiness_workflow.py`. Only this test file and this
follow-up's SDD report/review artifacts are owned. Do not edit workflow code,
T10 test files, package manifests, or the shared progress ledger.

## Acceptance

- Keep the test exercising real YAML parsing and its existing positive/damaged
  workflow fixtures; do not delete, skip, weaken, or replace behavioral
  assertions.
- Resolve the missing PyYAML typing diagnostic with a narrow and truthful
  boundary (a line-local import ignore with explanation is acceptable if no
  checked-in typed interface is justified; avoid `Any` spreading into the
  assertions and avoid blanket ignores).
- Run mypy on the file and focused pytest; run Ruff if applicable. Report the
  exact commands/results and create an independent-review snapshot.
- `.git` is read-only: no branches, worktrees, index writes, or commits.
