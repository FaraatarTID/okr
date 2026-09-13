# Provider Evidence Capture Checklist (Darkube + Hamravesh)

Documentation HQ: [README](../../README.md)

Purpose: capture only sanitized, reproducible evidence to close the remaining
repository-compliant 12-factor provider gaps.

## 1) Pre-flight (before any provider action)

- [ ] Confirm this repository runs are still passing:
  - `python scripts/verify_twelve_factor_contract.py`
  - `python scripts/verify_environment_parity.py`
  - `python scripts/verify_logging_contract.py`
  - `python scripts/verify_admin_process_contract.py`
  - `python -m pytest -q tests/test_twelve_factor_contract.py tests/test_environment_parity.py tests/test_admin_process_contract.py tests/test_admin_process_contract.py tests/test_recovery_evidence.py tests/test_rollback_evidence.py tests/test_prerelease_evidence.py`
- [ ] Collect required environment metadata:
  - Darkube namespace/project alias (sanitized only).
  - Commit SHA promoted for pre-release.
  - Operator identity for each action.
  - Target environment/customer identity.
- [ ] Confirm no production credentials are stored in repository artifacts.

## 2) Darkube staging evidence bundle

- [ ] Deploy from the staging workflow/run using immutable commit-SHA images.
- [ ] Record:
  - sanitized commit SHA
  - four app image refs and digests (web, bff, api, worker)
  - four Darkube build/deployment identifiers
  - private API/BFF/API/worker ingress URLs or IDs
  - staging secret/reference names used for DB URL and service secrets
- [ ] Verify and record:
  - [ ] web responds and is not in open error state
  - [ ] bff-health, api-health, worker health all pass
  - [ ] startup order allows API and worker dependent on DB availability
  - [ ] restart behavior (stop/restart one process, service recovers)
  - [ ] failure isolation (one failing service does not silently mask others)
  - [ ] structured logs available with request/correlation IDs
  - [ ] scaling and resource envelope are observed
- [ ] Build sanitized evidence JSON:
  - [ ] `commit`
  - [ ] `namespace`
  - [ ] `darkube_build_ids`: `web`, `bff`, `api`, `worker`
  - [ ] `health`: `passed|failed`
  - [ ] `restart`: `status: passed|failed`, `services: [...]`
  - [ ] `ingress`: `status: passed|failed`, checks for `web`, `bff-health`, `api-health`
  - [ ] `rollback_result`: `passed|not_run|failed`
  - [ ] `timestamp`
- [ ] Validate with:
  - `python scripts/verify_environment_parity.py --manifest release-manifest.json --evidence <sanitized-darkube-evidence>.json`
  - `python scripts/write_prerelease_evidence.py <sanitized-darkube-evidence>.json docs/saas/prerelease-evidence.md`

## 3) Application rollback rehearsal evidence

- [ ] Keep two immutable release descriptors ready (`release-0`, `release-1`).
- [ ] Deliberately deploy a second candidate.
- [ ] Trigger rollback on the platform using the previous known-good immutable IDs.
- [ ] Record:
  - old/new image digests and Darkube deployment identifiers
  - rollback reason and operator
  - health outcome post-rollback for web/BFF/API/worker
- [ ] Run the local verifier:
  - `python scripts/verify_rollback_evidence.py --record <rollback-record>.json`
- [ ] Mark in `[docs/saas/twelve-factor-evidence.md](../../docs/saas/twelve-factor-evidence.md)`:
  - `factor IX` and `factor V` provider-dependent row to covered with sanitized evidence.

## 4) Hamravesh backup and restore evidence (production path)

- [ ] Confirm provider product behavior once:
  - provider-issued backup ID and restore ID are available
  - backup policy and retention are explicit
  - restore target can be isolated and non-production
- [ ] Run isolated backup/restore rehearsal:
  - take provider backup
  - restore to a dedicated isolated target
  - validate health and integrity checks
- [ ] Capture and verify:
  - backup status/checksum
  - restore status/checksum
  - measured `measured_rpo_seconds`
  - measured `measured_rto_seconds`
- [ ] Validate sanitized evidence:
  - `python scripts/verify_recovery_evidence.py --evidence <hamravesh-evidence>.json --output <hamravesh-verification>.json`
- [ ] Update `[docs/saas/hamravesh-backup-onboarding.md](../../docs/saas/hamravesh-backup-onboarding.md)` with explicit PASS/FAIL/NOT_AVAILABLE with gate references.

## 5) Close and unblock production

- [ ] Merge provider evidence into `[docs/saas/twelve-factor-evidence.md](../../docs/saas/twelve-factor-evidence.md)` and clear PENDING rows.
- [ ] Set `provider_evidence: PASS` for environment parity.
- [ ] Ensure `phase-1-entry-evidence.md` includes:
  - named operations owner
  - rollback evidence
  - backup/restore evidence
  - measured RPO/RTO
- [ ] Re-run the repository gates after each evidence artifact lands:
  - `python scripts/verify_twelve_factor_contract.py`
  - `python scripts/verify_environment_parity.py`
  - `python scripts/verify_admin_process_contract.py`

## Fail-open rule

If any required provider item is `FAIL` or `NOT_AVAILABLE`, stop production
customer-data onboarding and keep `provider_evidence` at
`PENDING_PROVIDER_EVIDENCE` until the item is corrected and re-verified.
