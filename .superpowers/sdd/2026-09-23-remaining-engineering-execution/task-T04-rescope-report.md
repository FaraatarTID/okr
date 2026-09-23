Documentation HQ: [README](../../../README.md)

# T04 evidence-gate re-scope — 2026-09-23

## Decision and source check

Re-scoped T04 in `docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md` from new CI/promotion wiring to verification and disposition. The signed canonical register's Phase 1 progress row A3 (`docs/REMAINING_ENGINEERING_PLAN.md:226`) is Done: PR `backend-quality` already runs the full pytest suite, while the real evidence bundle belongs to production promotion. F6 remains open for genuine provider, measurement, attestation, owner and approval facts. No evidence was fabricated, and neither the register nor application/workflow code was changed.

Inspected `.github/workflows/promote-production.yml:118-145`: `phase-1-evidence` invokes `python scripts/check_saas_phase1_evidence.py`, and `approve-and-prepare` has `needs: [verify-staging, verify-signatures, phase-1-evidence]` plus the production environment. Inspected `.github/workflows/ci.yml:175,341,349`: `backend-quality` runs pytest. `tests/test_phase1_promotion_gate.py:48-103` checks the promotion job, its secret, its approval dependency, real-bundle absence from PR CI, and the pytest invocation. Source inspection found no A3 placement/wiring mismatch to justify new code. These checks were read, not re-run as behavioral tests or remote CI.

Updated T04's plan packet and self-scan, removed it from the workflow edit lane and test-author conflict edge, and adjusted the SDD ledger checklist/matrix/self-scan. The ledger has a `Ruling` with the cost of a missed regression and the exact-mismatch/scoped-plan-update response. Local T00/T01 cross-signoff remains recorded as PASS; this re-scope does not establish merge, remote CI, provider evidence, or deployment acceptance. Independent review of this T04 plan correction remains pending.

## Requested checks

`python scripts/check_docs_hq_links.py` — exit 0:

```text
Documentation HQ link check passed (91 markdown files scanned).
```

`python scripts/check_quality_gate_baseline.py` — exit 0:

```text
Quality baseline review date: 2026-09-23
- QG-002: expires 2026-11-15 | Repo-wide mypy remains staged; broad default coverage is active for scripts plus the runtime-core backend_app modules. Measured 2026-09-20: 127 errors in 24 of 347 checked files (src 10, tests 10, backend_app 2, scripts 2), led by arg-type 56, union-attr 16 and attr-defined 15.
Quality baseline check passed.
```

Direct structure and whitespace check — exit 0:

```text
plan_packets=36; exact_sequence=True
plan_self=36; exact_sequence=True
ledger_checklist=36; exact_sequence=True
ledger_self=36; exact_sequence=True
docs/superpowers/plans/2026-09-23-remaining-engineering-execution.md: trailing_whitespace_lines=0; final_newline=True; cr_bytes=0
.superpowers/sdd/2026-09-23-remaining-engineering-execution/progress.md: trailing_whitespace_lines=0; final_newline=True; cr_bytes=0
```
