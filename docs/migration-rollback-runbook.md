# Pre-SaaS Migration Rollback Runbook

Documentation HQ: [README](../README.md)

Status: `DOCUMENTED, BACKUP/RESTORE OPERATIONS IMPLEMENTED; PRODUCTION DRILL DEFERRED` for P0-06.

This runbook defines the release boundary and restoration path for the
architecture migration slices. It is intentionally bounded to application,
BFF, and database migration rollback; it does not authorize destructive
commands against a live environment.

## Versioned release operations

- Register an immutable artifact descriptor containing the backend, BFF, and web
  image references, release version, and artifact digest.
- Deploy only through `ReleaseManager.deploy(environment_id, release_artifact)`.
- The local adapter deploys the candidate, runs its health gate, and restores the
  previous artifact when the gate fails before reporting the deployment failure.
- Roll back through `ReleaseManager.rollback(environment_id, previous_artifact)`.
- Every operation records the previous version, target version, operator, health
  result, rollback result, digest, and timestamp.
- Local exercises use `scripts/deploy_saas_release.py` with descriptor files and
  `tmp/saas-release-state.json`; they do not start, stop, or modify live services.
- The adapter boundary is explicit: Compose receives pinned release image
  references through `OKR_RELEASE_BACKEND_IMAGE`, `OKR_RELEASE_BFF_IMAGE`, and
  `OKR_RELEASE_WEB_IMAGE`, while the local release command only plans and records
  promotion. It does not invoke Compose.
- After registration, the read-only command
  `python scripts/deploy_saas_release.py compose-env --environment-id ...
  --artifact ... --provisioning-state-file ...` emits the exact three Compose
  overrides. It requires the persisted provisioning and release state and does
  not start or modify services.

## Release boundary

- Record the deployed image digest, Compose file revision, Alembic revision, and environment profile before promotion.
- Keep the previous backend, BFF, and web images available for one release cycle.
- Capture backend health, BFF health, web reachability, and migration revision before and after promotion.
- Stop promotion if health, contract, or data-access mode checks fail.

## Application and BFF rollback

1. Set the deployment image references back to the recorded last-known-good digests.
2. Run `docker compose -f deploy/docker/docker-compose.yml up -d backend-api backend-worker spa-bff spa-web`.
3. Run `python scripts/verify_deploy_readiness.py --compose-file deploy/docker/docker-compose.yml --timeout-seconds 30 --retry-interval 1`.
4. Confirm the backend and BFF health endpoints, route allowlist, and SPA root response.
5. Preserve failed-container logs and the request/correlation identifiers for incident review.

## Database migration rollback

1. Freeze application promotion and record the current Alembic revision with `docker compose -f deploy/docker/docker-compose.yml exec -T backend-api alembic current`.
2. Confirm the target downgrade revision and data-loss impact with the migration owner.
3. Take the approved database backup before any downgrade.
4. Run the explicitly approved Alembic downgrade through the backend migration environment.
5. Restart the backend and worker, then rerun readiness, import-boundary, contract, and smoke checks.
6. If downgrade safety is uncertain, restore the approved backup instead of improvising a partial downgrade.

## Rehearsal record

### Current release-boundary snapshot

- Backend API and worker image: `okr-backend:local`, image `f6ff45d9d68f`.
- BFF image: `okr-spa-bff:local`, image `fdf48f393a2f`.
- Web image: `okr-spa-web:local`, image `972f5aa81c4b`.
- Postgres image: `postgres:16-alpine`, image `57c72fd2a128`.
- Current Alembic revision: `drop_global_cycle_index (head)`.
- Current Compose state: backend API and Postgres healthy; worker, BFF, and web running.
- Snapshot date: 2026-08-31.

### SaaS database profile smoke result

- A disposable database was created and migrated from an empty state through `drop_global_cycle_index`.
- A temporary API process started with `OKR_DEPLOYMENT_PROFILE=single_tenant_saas` and `OKR_DATA_ACCESS_MODE=database` and returned HTTP 200 from `/healthz`.
- The health payload reported `data_access_mode=database`, `configured_mode=database`, and `dead_jobs=0`.
- The disposable database was removed after the probe; this was a forward migration smoke test, not a rollback rehearsal.
- The persistent local database remains stamped with obsolete `baseline_2026_08_26_schema` metadata and must not be repaired by an unapproved stamp operation.

| Rehearsal | Status | Evidence required |
|---|---|---|
| Application/BFF image rollback | Not rehearsed | Previous image digests, readiness output, health output, and logs |
| Alembic downgrade or backup restore | Not rehearsed | Database backup identity, revision before/after, migration output, and smoke results |
| Wrapper-level recovery | Not rehearsed | Wrapper command output and service-state comparison |

## Safety rules

- Never run a downgrade against production without an approved backup and named owner.
- Never treat a healthy process as proof that data compatibility is preserved.
- Never remove the previous image or migration artifact until the release boundary expires.
- Update this record after every rehearsal and link the evidence from the P0-06 status ledger.

## Pre-SaaS release decision

The versioned release mechanism is implemented and can be exercised with two
deployable artifact descriptors. The owner has explicitly deferred live
application rollback rehearsal under the disposable pre-SaaS risk acceptance.
Before production SaaS data is stored, the operator must select retained image
digests, run a real deployment and rollback rehearsal, and attach health and
rollback evidence here.
## Execution update: 2026-09-01

- The running backend's actual compatibility database is the Supabase PostgreSQL target, not the local Compose `postgres` database.
- The runtime target was independently queried and reported Alembic revision `drop_global_cycle_index (head)`.
- A PostgreSQL 17-compatible custom-format backup of the live runtime database was captured at `tmp/okr-runtime-pre-rollback-rehearsal.dump`.
- The backup was restored into an isolated PostgreSQL 17 rehearsal instance with `pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error`; restore exit code was `0`, and the restored public schema contained 23 tables. The rehearsal instance was removed afterward.
- The live runtime database was not modified by the backup or restore rehearsal.
- The database backup/recovery condition is now evidenced. P0-06 remains `IN-PROGRESS` only for the application release rollback rehearsal and release-artifact selection.
## Owner decision: disposable pre-SaaS database - 2026-09-01

For the disposable pre-SaaS phase, the owner explicitly waived database dump, migration, and database rollback work while the runtime database contained disposable mock data. The application schema remains in place and all application data has been purged. This exemption applies only to the disposable phase and does not waive the future SaaS backup/recovery requirement.
## Phase disposition: disposable pre-SaaS - 2026-09-01

The owner’s explicit risk acceptance was limited to disposable mock data and is not a production approval. This runbook remains the required starting point for the SaaS persistence phase; it must be completed with provider-supported backups, isolated restore evidence, application release rollback rehearsal, RPO/RTO targets, and an operational owner before real tenant data is stored.

## Isolated two-artifact rollback rehearsal - 2026-09-01

- Descriptor A: `env-acme`, version `2026.09.0`, pinned images with digest
  `sha256:0000000000000000000000000000000000000000000000000000000000000000`.
- Descriptor B: `env-acme`, version `2026.09.1`, pinned images with digest
  `sha256:1111111111111111111111111111111111111111111111111111111111111111`.
- The local adapter promoted B, then rolled back to registered A.
- Focused tests evidence `DEPLOYED`, rollback to A, persisted records, environment
  binding, and candidate removal after a failed health gate.
- Failed candidate artifacts remain registered and persisted for auditability, but
  they are removed from the active deployment before the `ROLLED_BACK` result is
  returned.
- This was an isolated adapter rehearsal only. No Compose command, live service,
  customer environment, or production deployment was involved.

## Provider-backed backup and isolated restore operations - 2026-09-01

- `BackupManager.create(environment_id)` requires a provider-issued backup
  identifier, provider name, checksum, retention class, operator identity, and
  configured RPO/RTO targets.
- `BackupManager.verify(backup_id)` computes a canonical SHA-256 over the
  provider verification payload and compares it with the provider checksum;
  presence-only verification is not accepted. It also records backup freshness,
  last-success, and last-failure status.
- Provider `create_backup` failures persist a complete failed backup status,
  including timestamp, operator, retention, RPO/RTO, and error, even when no
  provider backup identifier was issued.
- Provider `verify_backup` failures persist the complete existing backup status
  with the failure timestamp and error before re-raising.
- `RestoreManager.restore(backup_id, isolated_target)` rejects false, empty, and
  `live`/`production`/`prod` targets before calling the provider. Live restore is
  prohibited by the operation boundary, not merely by CLI convention.
- `BackupProvider` and `RestoreProvider` are separate production contracts.
  They require provider-issued identifiers, provider verification, and a
  provider-reported restore duration. No cloud provider is selected yet.
- `LocalBackupProvider` is explicitly **TEST-ONLY**. It is metadata-only and
  isolated: it does not connect to PostgreSQL, invoke `pg_dump`, or modify
  services. Production CLI execution refuses this adapter unless `--test-only`
  is explicitly supplied.
- Lifecycle CLIs require `OKR_OPERATOR_TOKEN` verified against an operator
  credential file supplied by `--credential-file` or
  `OKR_OPERATOR_CREDENTIAL_FILE`. A missing, blank, invalid, or unassigned
  credential is rejected; there is no operator-name or insecure default.
- Persisted status includes last success, last failure, freshness, retention,
  RPO/RTO policy, checksum, provider, operator, failure reason, and
  restore-test status. Checksum and stale failures persist this complete status
  before raising.
- Focused evidence: `python -m pytest tests/test_saas_backup_operations.py -q`
  returned `18 passed in 0.36s`.
- Isolated restore drill: provider `local-isolated`, explicitly registered
  target `rehearsal-db-1`, provider backup identifier generated with the
  `provider-backup-` prefix, SHA-256 verified, measured elapsed duration
  recorded, restore-test status persisted as `PASSED`, and cleanup is disposal
  of the isolated adapter state. No live database or application data was
  touched.
- Restore rejects unregistered targets, environment-mismatched targets, and
  broad live/production-like identifiers or URLs before provider invocation.
- The restore CLI never marks its supplied target as registered. The target must
  already exist in the supplied backup/target state file through explicit
  provider registration. Unknown targets fail before backup verification or
  restore provider invocation.
- Verification and provider failures persist restore-test status `FAILED`, the
  error, timestamp, and measured elapsed time before the error is raised.
- Production SaaS remains gated on selecting a real provider, configuring
  retention/RPO/RTO, proving provider-supported restore, and assigning an
  accountable operator. This local drill is implementation evidence, not
production disaster-recovery evidence.

## Production persistence onboarding gate

Before the first real customer record is stored, the release owner must attach
the passing `just saas-evidence` result to this runbook. The evidence bundle
must identify the target environment and customer and must include:

1. A provider-supported backup, provider-issued backup ID, retention policy,
   checksum/integrity verification, and freshness result.
2. A restore from that backup into a registered isolated target, provider-issued
   restore ID, integrity result, measured restore duration, and cleanup record.
3. Approved RPO/RTO targets and numeric measured recovery results from the
   provider-backed drill.
4. Named decision and platform/operations owners, with authenticated operators
   recorded for the backup and restore actions.
5. Immutable application release rollback evidence and explicit approval to
   onboard real data.

The gate is fail-closed: local/test adapters, synthetic release fixtures,
empty databases, prose-only claims, or the historical disposable pre-SaaS risk
acceptance are not production evidence. This does not change disposable
pre-release behavior; it only prevents that environment from being mistaken
for a production recovery control.

## Task 7 entry-gate handoff (2026-09-01)

The Phase 1 evidence record is [docs/saas/phase-1-entry-evidence.md](saas/phase-1-entry-evidence.md). This runbook records the boundary between local contract evidence and production recovery evidence.

Current disposition:

- Application release rollback: local isolated adapter evidence exists for separately registered, immutable synthetic release artifacts `release-0` and `release-1`; failed health returns to the prior artifact and explicit rollback records operator/version data. Provider-backed rollback: **NOT AVAILABLE - provider/artifact not selected**.
- Synthetic release fixture digests: `release-0` = `sha256:dc653afb00e8d53f9c94ff5f1bbec0de9ad7f76889af79f46efe9356b95c02fd`; `release-1` = `sha256:c2e19570b6aee82937bf4b09640059646a6985f80b1b16b91924f92a751a75a0`. These are generated test values, not registry artifacts.
- Backup and restore: `LocalBackupProvider` metadata-only evidence creates a `provider-backup-*` record for `env-a`, verifies its SHA-256 checksum, registers isolated target `rehearsal-db-1`, and records a successful verified restore with measured non-negative elapsed/RTO values. Evidence is exercised by `tests/test_saas_backup_operations.py`; the checksum-failure persistence fixture is `.test-artifacts/backup-checksum-failure.json`.
- Provider backup/restore, retention enforcement, measured provider RPO/RTO, and provider restore timing: **NOT AVAILABLE - provider/artifact not selected**.
- Owners: repository owner accepts the pre-SaaS deferral; platform/operations owner: **UNASSIGNED**; each local rehearsal uses operator fixture `operator-a`.

The current empty/mock-data pre-SaaS database does not justify production recovery closure. This is an intentional phase boundary, not evidence that production recovery is complete.
