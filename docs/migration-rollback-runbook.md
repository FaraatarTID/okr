# Pre-SaaS Migration Rollback Runbook

Documentation HQ: [README](../README.md)

Status: `DOCUMENTED, NOT YET REHEARSED` for P0-06.

This runbook defines the release boundary and restoration path for the
architecture migration slices. It is intentionally bounded to application,
BFF, and database migration rollback; it does not authorize destructive
commands against a live environment.

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
- A temporary API process started with `OKR_DEPLOYMENT_PROFILE=saas` and `OKR_DATA_ACCESS_MODE=database` and returned HTTP 200 from `/healthz`.
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
## Execution update: 2026-09-01

- The running backend's actual compatibility database is the Supabase PostgreSQL target, not the local Compose `postgres` database.
- The runtime target was independently queried and reported Alembic revision `drop_global_cycle_index (head)`.
- A pre-reconciliation custom-format dump of the local Compose database was captured and catalog-verified at `tmp/okr-pre-alembic-reconcile.dump`; it was used for a disposable restore rehearsal only.
- The disposable restore rehearsal was completed against `okr_rollback_rehearsal` with `pg_restore -U okr`, and the disposable database was removed afterward. This proves restore mechanics for the local PostgreSQL 16-compatible artifact, not recovery of the live Supabase database.
- A provider-native or PostgreSQL 17-compatible backup of the live runtime database could not be produced from this environment: the available client initially rejected the PostgreSQL 17.6 server as a PostgreSQL 16 client, and the PostgreSQL 17 client path did not complete. No live data was changed by those attempts.
- P0-06 therefore remains `IN-PROGRESS`. The live backup/recovery proof and combined application-plus-database rollback rehearsal remain prerequisites before tenant/RLS schema work.
## Owner decision: disposable pre-SaaS database - 2026-09-01

For the current pre-SaaS phase, the owner has explicitly waived database dump, migration, and database rollback work because the runtime database contains disposable mock data. The application schema remains in place, all application data has been purged, and database recovery rehearsal is deferred until persistent SaaS data exists. This section supersedes the earlier backup-oriented execution notes for this phase only.
