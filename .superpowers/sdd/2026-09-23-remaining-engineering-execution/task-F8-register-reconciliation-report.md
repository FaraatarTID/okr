Documentation HQ: [README](../../../README.md)

# F8 canonical register reconciliation — 2026-09-23

## Decision and scope

Edited only the F8 progress row in `docs/REMAINING_ENGINEERING_PLAN.md` and appended one `Ruling` to this SDD progress ledger. T07's implementation report and scoped re-review are PASS; the coordinator retains control of the T07 checklist. No application or workflow code was edited.

F8 is **Done locally for the 25-script inventory and deterministic repository-gate decision**. The original 25 scripts had no direct invocation in workflows, `justfile`, or pre-commit. T07 now places `verify_observability_readiness` and `verify_ops01_readiness` in an unconditional `repository-readiness` job required by `ci-result`. The other 23 comprise seven imported/executed helpers and sixteen operator/developer commands with no direct invocation in those three enforcement surfaces or Python helper import. The four admin CLIs are source-read by `verify_admin_process_contract.py`; that is neither an import nor an execution. `jan_context` has a PowerShell launcher call outside those enforcement surfaces. All 25 have explicit dispositions; none was proven dead or deleted.

The register now preserves the limits: static readiness checks do not certify deployed telemetry or a live restore, and provider, topology, rollback and release-pair evidence remain with their owner/operator gates. Hosted CI and branch protection were not verified. The ledger ruling records the cost of misclassifying operator tools as dead or static checks as live evidence.

## Evidence and checks

`task-T07-report.md` lists all 25 dispositions; `task-T07-rereview.md` records PASS after correcting the four source-inspection descriptions. `.github/workflows/ci.yml:610-650` contains both `python -m scripts.X` commands, the `repository-readiness` job in `ci-result.needs`, and its result in the aggregate failure loop. The T07 report records 30 passing focused tests, including positive and damaged fixtures; these tests were not rerun for this register-only edit.

Targeted report/workflow assertion — exit 0:

```text
report_rows=25; ci_gate=2; imported_helper=7; operator_command=16; f8_rows=1; ci_job=True; ci_result_need=True; observability_module=True; ops01_module=True
```

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

`git diff --check -- docs/REMAINING_ENGINEERING_PLAN.md` — exit 0, no output. Direct checks on the register and ledger found zero trailing-whitespace lines and CR bytes, with final newlines in both files.

## Durability addendum — final row for scoped re-review

Removed the canonical F8 row's link to the gitignored SDD T07 report. The authoritative row now names both CI checks, all seven helper scripts, and all sixteen retained operator/developer scripts. It cites repository paths `.github/workflows/ci.yml` and `tests/test_repository_readiness_workflow.py` for the two required checks. The four admin CLIs are identified as source-inspected, not imported or invoked; `jan_context`'s PowerShell launcher call remains distinguished from the three enforcement surfaces. The T07 checklist was not changed.

Re-ran the targeted assertion against the 25 numbered T07 report rows and the final F8 row — exit 0:

```text
report_rows=25; ci_gate=count=2, missing_in_F8=0; imported_helper=count=7, missing_in_F8=0; operator_command=count=16, missing_in_F8=0; f8_rows=1; hidden_sdd_citation=False; tracked_ci_citation=True; test_citation=True
```

Re-ran Docs HQ (`Documentation HQ link check passed (91 markdown files scanned).`), quality baseline (same exact output above), and `git diff --check -- docs/REMAINING_ENGINEERING_PLAN.md` (exit 0, no output). Direct whitespace checks again found zero trailing-whitespace lines and CR bytes, with final newlines in the register and ledger. The final row awaits independent scoped re-review; this addendum does not claim its approval.
