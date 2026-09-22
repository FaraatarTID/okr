# Single-Tenant Fleet Rollout Runbook

Use the `Migrate SaaS tenant databases` workflow only after a release has passed
the compatibility gate. Supply an incident/change reference for every run.

Before registering the first tenant, provision the dedicated PostgreSQL database
and run `uv run python scripts/bootstrap_fleet_control_plane.py
--control-plane-url "$SAAS_CONTROL_PLANE_URL"`. This schema is intentionally
separate from tenant application schemas; do not run the tenant Alembic chain
against it.

- Start with one tenant (`tenant`) and `max_concurrency=1`; verify the generated
  report and tenant health before removing the tenant filter.
- The default fleet limit is 10 concurrent migrations. Stop the rollout on any
  failure; rerun only after a forward fix or operator-approved recovery.
- Migrations are expand-only. Never invoke Alembic downgrade in production.
  Roll back application images only when their declared schema range remains
  compatible with the migrated schema.
- Preserve the workflow report as operational evidence. Manual Darkube actions
  must include the same incident/change reference and signed evidence payload.
- Deploy an application image only through `deploy_saas_release.py` with the
  fleet control-plane URL, completed rollout ID, and incident reference. The
  gate rejects an image whose immutable digest or version does not exactly match
  the migration rollout.
