# SDD ledger — plan: docs/superpowers/plans/2026-09-02-twelve-factor-compliance-plan.md

## Preflight

| Task | Shared files/interfaces | Result |
|---|---|---|
| 1 and 6 | README.md and evidence documentation | Ledger documentation is coordinated locally; parity agent avoids these files. |
| 3 and 6 | CI/release workflows and deployment manifest | Sequential integration required after disjoint repository slices complete. |
| 4 and 5 | Runtime processes and observability | Logging agent is limited to logging scope; process contract follows its results. |
| 7 and 8 | Deployment operations and provider evidence | Repository checks can close only local prerequisites; provider evidence remains external. |

| Task | Internal consistency |
|---|---|
| 1 | Consistent with dedicated-server-per-customer architecture and provider evidence rules. |
| 2 | Consistent with environment-driven secrets and locked dependencies. |
| 3 | Consistent with immutable GHCR promotion. |
| 4 | Consistent with separate API, worker, BFF, and web processes. |
| 5 | Consistent with stdout/stderr event-stream logging and secret redaction. |
| 6 | Consistent with CI/staging/production parity requirements. |
| 7 | Consistent with disposable local PostgreSQL checks and separate production recovery. |
| 8 | Consistent with provider-dependent evidence remaining pending until executed. |

Ruling: Darkube and Hamravesh operations will be recorded as pending provider evidence rather than simulated — provider access is unavailable and fabricated evidence would invalidate the ledger.

## Progress

- Task 1: in progress (evidence ledger created locally)
- Task 1: complete (evidence ledger created and linked from README)
- Task 4: complete (process contract verifier and environment-driven web port)
- Task 5: complete (logging contract verifier, redaction checks, and operations guidance)
- Task 6: complete (environment parity verifier and provider-pending evidence rules)
- Task 7: complete (admin-process verifier and explicit recovery boundary)
- Task 3: complete (repository contract gate wired into CI; immutable promotion checks covered)
- Task 2: complete (existing locked dependency and environment configuration gates covered)
- Task 8: pending provider evidence (Darkube deployment, application rollback rehearsal, and Hamravesh backup/restore)
- Review loop: complete (factors VI, VIII, IX, and XI strengthened with runtime fixes and regression tests)
- Review loop: complete (full suite 948 passed, 8 skipped; Ruff, mypy, Compose, docs, and contract gates passed)
- Task 8: remains pending provider evidence by explicit environment constraint
