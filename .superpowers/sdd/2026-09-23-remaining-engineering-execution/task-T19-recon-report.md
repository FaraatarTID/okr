Documentation HQ: [README](../../../README.md)

# T19/D8 read-only reconnaissance

## Finding

No current target account-shape evidence is available locally. The register's one-row `admin` count from 2026-09-20 explicitly remains historical. No database was queried during this reconnaissance.

## Repository evidence

- `src/models.py:125-155`: `User.username` is unique/indexed; no email, issuer, subject, or external identity field.
- `alembic/versions/baseline_2026_08_26_schema.py:347-379`: baseline user table/index has username but no email/external subject or identity-link table; repo search found no later link migration.
- `backend_app/routers/platform_routes.py:131-153`: `/v1/auth/me` matches `User.username` to the actor.
- `backend_app/schemas.py:144-159`: user create schema contains username/password/role/profile IDs, no email/link fields.
- `src/saas/provisioning.py:1-6,208-212`: provisioner is metadata-only and does not connect to or write customer DBs.
- `src/saas/identity_ports.py:1-7`: contracts/test doubles only, not production identity provisioning.
- `src/saas/identity_contract.py:403-407,482-489`: email mapped as actor/username in a Python compatibility contract; not proof of production account linking.
- `docs/REMAINING_ENGINEERING_PLAN.md:113` and T19 packet in execution plan: current target recount, invariant confirmation, migration freeze resolution, and authorized bootstrap/backfill are prerequisites.

## Disposition

Safe work is limited to an acceptance outline: verified `(iss, sub)` link to exactly one existing provisioned account; unlinked or ambiguous identities reject; no email fallback; no just-in-time users. Keep schema/cardinality/uniqueness decisions open pending target counts and owner authorization. Production migration, backfill, exchange route, and API artifact chain remain blocked.
## 2026-09-26 status — target evidence gate remains open

The current checkout still contains only the historical 2026-09-20 aggregate count; no current target database was queried. The T19 integration/migration work remains blocked until current non-identifying target aggregates confirm username/email shapes and issuer/subject link uniqueness, and the identity/migration owners provide an approved freeze resolution and bootstrap/backfill path. The coordinating agent requested those aggregate facts and approvals from the user without credentials or raw account rows. Until supplied, do not add schema, migrate/backfill users, or expose exchange integration. The verified issuer/subject link acceptance outline above remains the safe design preparation.
