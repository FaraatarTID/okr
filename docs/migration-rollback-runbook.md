# Pre-SaaS Migration Rollback Runbook

Back to [Documentation HQ](README.md).

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
