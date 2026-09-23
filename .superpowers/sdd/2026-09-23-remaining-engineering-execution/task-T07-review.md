Documentation HQ: [README](../../../README.md)

# T07 independent review

Verdict: **PASS with one low-severity report correction**. No blocking implementation findings.

## Findings

- **LOW — inventory evidence describes source inspection as an import.** Rows 1–4 of `task-T07-report.md` say that `verify_admin_process_contract.py` imports `backup_saas_environment`, `deploy_saas_release`, `restore_saas_environment`, and `verify_recovery_evidence`. In fact, `scripts/verify_admin_process_contract.py:33–38` reads those files as text using `_read`; it neither imports nor executes them. Change those four evidence cells to “source inspected by the CI-gated admin-process contract checker” and retain their operator-command classifications. This does not invalidate the disposition or justify adding live operations to PR CI, but it matters when later agents distinguish structural contract checks from execution coverage.

## Verified acceptance

- The report contains all 25 named F8 scripts, with a primary disposition and retention/enforcement rationale. The caller scan confirms the helper import chains for required insert columns, evidence metadata and topology validators; renderer execution through the twelve-factor checker; demo-seed execution through the development workflow; and Jan invocation by the PowerShell launcher. Operator scripts require explicit environment, evidence, installation, database or provider inputs. No script was deleted or changed by T07.
- `.github/workflows/ci.yml:609` adds an unconditional job with no path filter, `if`, secrets, provider configuration or `continue-on-error`. Both new invocations use `python -m scripts.X`.
- `ci-result` needs `repository-readiness`, reads its result into `READINESS_RESULT`, and includes that variable in the failure/cancellation loop. The workflow has PR and push triggers. Remote branch protection and an actual hosted run were not established by this local review.
- Both new scripts are deterministic static checks using only `pathlib`. `verify_ops01_readiness` reads the OPS guide, source files and migration markers; it does not import runtime code, connect to a database, restore data, load environment secrets or assert production facts. Its successful outcome establishes the static contract only, as the implementation report explicitly states.
- `tests/test_repository_readiness_workflow.py` parses the real workflow, extracts each actual command, invokes its module in a subprocess against a temporary fixture root and checks successful output. It then removes a required marker and requires a nonzero exit plus the named missing marker. These are real pass/fail executions of the checkers, not mocked command success. Their scope is appropriate for wiring pre-existing static contracts; they do not purport to validate deployed observability or operational restoration.
- The existing OPS backup/restore fixture additionally exercises an actual isolated database roundtrip and rejects a bad backup-format version. Provider-backed commands, topology evidence validation and release-pair validation remain outside ordinary PR CI.

## Independent verification

Executed:

`.venv\Scripts\pytest.exe -q tests/test_repository_readiness_workflow.py tests/test_ops01_readiness.py tests/test_rollback_workflow_wiring.py tests/test_justfile_contract.py`

Result: **30 passed**, with the existing `.pytest_cache` write-permission warning only. Inspected the actual working-tree workflow/test changes, checker source, all 25 dispositions, caller searches across enforcement surfaces/scripts/tests, and the F8 register and packet acceptance requirements. No production/provider operations were invoked.
