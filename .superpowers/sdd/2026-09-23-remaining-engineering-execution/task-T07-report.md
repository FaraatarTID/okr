# T07 implementation report — script enforcement inventory

Status: implementation ready for independent review; packet not marked complete.

## Change and decision

Added an unconditional `repository-readiness` job to `.github/workflows/ci.yml`.
It runs `python -m scripts.verify_observability_readiness` and
`python -m scripts.verify_ops01_readiness` and is a required `ci-result` need.
Both scripts inspect committed repository files with only the Python standard
library. They require no provider, target, secret, real data, or local package
installation. `tests/test_repository_readiness_workflow.py` parses the actual
workflow, confirms the job is unconditional and required by `ci-result`, then
executes each workflow command against a copied passing fixture and a damaged
fixture that must fail. The test also checks the result variable reaches the
aggregate failure loop. The existing OPS-01 CLI test now invokes the module
with `-m`, matching the packet's package-invocation rule. No script was removed.

I scanned every `.github/workflows/*.yml`, `justfile`, and
`.pre-commit-config.yaml` for the 25 names; the only direct enforcement matches
after this change are the two new commands. I then searched `scripts/`,
`tests/`, and application/deployment sources for callers, and read each script's
CLI behavior. A test import by itself is evidence of coverage, not production
invocation. The categories below describe primary use; the evidence column
also records secondary use or source inspection. “Operator command” includes local development
and release preparation commands that require an explicit user and inputs.

## Complete 25-script disposition

| # | Script (`scripts/*.py`) | Class | Caller or enforcement evidence and disposition |
|---:|---|---|---|
| 1 | `backup_saas_environment` | Operator command | Provider-backed backup CLI; `verify_admin_process_contract.py` reads its source with `_read` but does not import or invoke it. CLI bootstrap tests cover it. Requires environment/provider state; keep operator-only. |
| 2 | `deploy_saas_release` | Operator command | Release/rollback CLI; `verify_admin_process_contract.py` reads its source with `_read` but does not import or invoke it. CLI bootstrap tests cover it. Requires environment artifact and state; keep operator-only. |
| 3 | `restore_saas_environment` | Operator command | Isolated-target registration/restore CLI; `verify_admin_process_contract.py` reads its source with `_read` but does not import or invoke it. Backup and bootstrap tests cover it. Requires provider and isolated target; keep operator-only. |
| 4 | `verify_recovery_evidence` | Operator command | Recovery-evidence CLI; `verify_admin_process_contract.py` reads its source with `_read` but does not import or invoke it. `tests/test_recovery_evidence.py` and doc-schema tests cover it. Real signed recovery bundle and key material belong to promotion/operations, not PR CI. |
| 5 | `render_k8s_release` | Imported helper | `verify_twelve_factor_contract.py` invokes its renderer in a bounded subprocess; corresponding twelve-factor tests exercise it. A real release additionally supplies two image digests. No duplicate direct gate. |
| 6 | `required_insert_columns` | Imported helper | Constants imported by CI-gated `check_insert_contract.py` and its API-mode tests. No CLI or independent gate. |
| 7 | `evidence_metadata` | Imported helper | Imported by `compare_topology_evidence.py` and the three `validate_*` modules plus `validate_topology_review.py`. No standalone CLI. |
| 8 | `compare_topology_evidence` | Operator command | `tests/test_compare_topology_evidence.py` covers comparison; ADR documents an explicit topology comparison command. Needs captured current/target evidence; keep operator-only. |
| 9 | `seed_dev_demo` | Imported helper | Called by `scripts/dev_workflow.py`, which has `just dev-seed`; its own CLI has a disposable-environment guard and tests. Do not seed PR CI. |
| 10 | `validate_failure_isolation` | Imported helper | Imported by aggregate `validate_topology_review.py`; direct fixture tests exist. Actual failure-isolation evidence needs a deployed target and operator capture. |
| 11 | `validate_rollback_rehearsal` | Imported helper | Imported by aggregate `validate_topology_review.py`; direct fixture tests exist. Actual rollback evidence needs a rehearsal and measured outcome. |
| 12 | `validate_security_parity` | Imported helper | Imported by aggregate `validate_topology_review.py`; direct fixture tests exist. Current topology evidence remains pending on security controls; keep fail-closed operator validation. |
| 13 | `ai_provider_health_check` | Operator command | `docs/TROUBLESHOOTING.md` documents provider diagnosis; the CLI can run a live probe and depends on provider configuration. No safe default PR input. |
| 14 | `capture_compose_resources` | Operator command | Docker Compose resource capture CLI with tests in `test_capture_compose_resources.py`; requires a running topology and release/operator metadata. |
| 15 | `db_tcp_probe` | Operator command | Probes `OKR_DATABASE_URL` TCP reachability; no repository caller found. The database target is external and environment-specific. |
| 16 | `generate_baseline_migration` | Operator command | One-shot migration generator writes the baseline migration file from current models; no caller found. Running it as a check would mutate a frozen artifact. |
| 17 | `jan_context` | Operator command | Local Jan router discovery utility; `scripts/okr-launcher-ui.ps1` calls it. Not dead and not a CI contract. |
| 18 | `perf_hotpaths` | Operator command | Local database benchmark that seeds data; no caller found. Needs a disposable database and measured environment. |
| 19 | `seed_performance_fixture` | Operator command | Explicit `--confirm-disposable` and database-mode guards; `tests/test_seed_performance_fixture.py` covers it. Never seed ordinary PR infrastructure. |
| 20 | `supabase_https_probe` | Operator command | HTTPS probe documented in `TROUBLESHOOTING.md` and `OBSERVABILITY_AND_RUNBOOKS.md`; needs live Supabase endpoint/key. |
| 21 | `validate_topology_review` | Operator command | Aggregates four evidence categories and is documented in `BFF_RUNTIME_SMOKE_CHECKLIST.md`; tested in `test_validate_topology_review.py`. Current artifacts are pending, so a PR gate would fail every change independent of its content. |
| 22 | `verify_e2e_environment` | Operator command | Local Playwright installation and `node_modules` prerequisite probe; requires local binaries and project installation. The `spa-e2e` CI job already installs and runs the actual Playwright test. |
| 23 | `verify_observability_readiness` | CI gate | New `repository-readiness` command and positive/negative workflow-command fixture test. The check is a static document marker contract, not proof of deployed telemetry. |
| 24 | `verify_ops01_readiness` | CI gate | New `repository-readiness` command and positive/negative workflow-command fixture test; existing `test_ops01_readiness.py` covers success and backup/restore behavior. The static marker check does not replace a live restore drill. |
| 25 | `verify_release_pair` | Operator command | `tests/test_release_pair.py` covers valid/invalid pairs and the CLI requires two signed manifests plus each manifest's Cosign references. No workflow caller; the current rollback workflows validate their own manifest/evidence contracts. Adding this as a release gate needs a named artifact source and rollout placement, so it remains an explicit release-preparation command. |

No member was proven dead: even the scripts without repository callers expose
documented or plausible explicit diagnostic, seed, generation, or verification
commands. The independent F8 inventory is therefore closed as a classification
and repository-local wiring decision, while real execution evidence remains
with the relevant operator/release gates. In particular, topology validation
requires truthful `passed` artifacts for rate limiting and Origin control;
release-pair enforcement needs an owner to choose the source and placement of
its two signed manifests. T07 does not infer those facts or wire either to PR CI.

The canonical F8 row in `docs/REMAINING_ENGINEERING_PLAN.md` calls these four
source inspections imports. Its caller evidence and derived import count need a
separate coordinator-owned register reconciliation. The T07 correction changes
only inventory wording; no code change follows from it.

## Verification

- `python -m scripts.verify_observability_readiness`: exit 0, 13 sections and 2 links.
- `python -m scripts.verify_ops01_readiness`: exit 0.
- `.venv\\Scripts\\pytest.exe -q tests/test_repository_readiness_workflow.py tests/test_ops01_readiness.py tests/test_rollback_workflow_wiring.py tests/test_justfile_contract.py`: 30 passed. Both newly wired commands were run with passing and deliberately damaged fixtures.
- `python -m scripts.check_ci_script_references`: pass.
- `python -m scripts.check_workflow_secret_prerequisites`: pass, 26 declared secret references across 14 workflows.
- `.venv\\Scripts\\ruff.exe check tests/test_repository_readiness_workflow.py`: pass.

The focused pytest run emitted only the existing cache warning: it could not
write `.pytest_cache` under this managed filesystem. The report and
`task-T07-review.diff` are review artifacts. The shared progress ledger is
untouched; no Git index, branch, worktree, or commit write was attempted.
