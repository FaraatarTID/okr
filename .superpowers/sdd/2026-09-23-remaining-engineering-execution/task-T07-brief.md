Documentation HQ: [README](../../../README.md)

# T07 — Script enforcement inventory

## Objective

Resolve F8 by classifying its complete 25-script set and wiring only deterministic,
repository-local checks to an enforcement surface. Real-provider and operator
work stays in release/operations. Remove a script only after proving it is dead.

## Source and required script inventory

Use F8 in `docs/REMAINING_ENGINEERING_PLAN.md` as authority. Account for every
one of these 25 names in the report:

`backup_saas_environment`, `deploy_saas_release`,
`restore_saas_environment`, `verify_recovery_evidence`,
`render_k8s_release`, `required_insert_columns`, `evidence_metadata`,
`compare_topology_evidence`, `seed_dev_demo`, `validate_failure_isolation`,
`validate_rollback_rehearsal`, `validate_security_parity`,
`ai_provider_health_check`, `capture_compose_resources`, `db_tcp_probe`,
`generate_baseline_migration`, `jan_context`, `perf_hotpaths`,
`seed_performance_fixture`, `supabase_https_probe`,
`validate_topology_review`, `verify_e2e_environment`,
`verify_observability_readiness`, `verify_ops01_readiness`,
`verify_release_pair`.

The register notes which scripts are imported helpers and which currently have
no caller. Re-scan callers and every workflow, `justfile`, and
`.pre-commit-config.yaml`; do not assume that historical F8 lists are current.

## Owned files

- `.github/workflows/ci.yml` and only additional workflow file(s) proven
  necessary for a deterministic check
- `justfile` and/or `.pre-commit-config.yaml` only where justified
- focused wiring tests for any new or changed gate
- scripts only for a minimal invocation/contract fix; do not remove code without
  a demonstrated no-caller/no-operator-use case

Do not edit the authoritative register, unrelated workflows, app code, lockfiles,
or historical docs. Record the full classification matrix in `task-T07-report.md`
so it remains reviewable even if only some scripts are wired.

## Acceptance and safety

- Classify each named script as CI gate, operator command, imported helper, or
  dead code, citing caller/enforcement evidence.
- Wire only deterministic repository checks to CI/`just`; every new gate has
  positive and negative fixture coverage and a wiring test that proves workflow
  execution. Use `python -m scripts.X`, never `python scripts/X.py`.
- Keep checks requiring live providers, secrets, a deployment target, production
  facts, or real data out of ordinary PR CI. Put them in an existing release or
  operator path only when its evidence contract is clear; otherwise leave them
  as explicit operator commands.
- Confirm repository callers before any removal. If a disposition needs an
  owner/policy decision or would expand beyond F8, stop and report the exact
  blocker instead of guessing.
- Run the focused gate tests plus existing related tests; run docs/workflow
  checks appropriate to changed files. Report pre-existing failures separately.

## Workflow

Use one implementer and an independent reviewer. Preserve current user changes.
The managed `.git` directory is read-only: no branch, worktree, index, or commit
writes. One implementer owns the workflow/test lane at a time. Do not edit the
shared progress ledger; the coordinator updates it after review.
