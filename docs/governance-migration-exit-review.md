# Governance, Migration Safety, and Exit Review

Documentation HQ: [README](../README.md)

Status: `IN-PROGRESS` for P0-06.

This document defines the minimum governance and recovery contract before the pre-SaaS architecture can be treated as ready for a SaaS transition. It is a control artifact, not a claim that the rehearsals or checks have already passed.

## Ownership

| Control | Accountable owner candidate | Required evidence |
|---|---|---|
| Architecture boundary decision | Architecture | Approved ADR or boundary record linked from the status ledger |
| Runtime and deployment profile | Platform | Reproducible command, selected profile, and readiness output |
| Schema migration | Backend and data owner | Migration plan, compatibility window, and downgrade limitation |
| Release rollback | Platform and release owner | Rehearsed commands and last-known-good artifact |
| Security and session boundary | Security and platform | Review of API, BFF, secrets, and authorization behavior |
| Exit review | Architecture and delivery | Criteria checklist, open risks, and explicit disposition |

## Migration safety contract

Schema changes must be compatible with the application versions that can coexist during deployment and rollback. The preferred sequence is:

```text
expand schema -> deploy compatible readers/writers -> backfill or migrate data
  -> switch behavior -> contract old schema only after rollback window closes
```

For each Alembic migration, the owner must document:

- the affected tables, indexes, constraints, or data;
- whether the migration is additive, transformative, or destructive;
- the application versions that can read and write the intermediate state;
- whether downgrade is safe, partial, or prohibited;
- the backup or restore point required before execution;
- the observation window before contracting or deleting old structures.

## Migration safety register

| Migration | Affected objects | Classification | Compatible versions | Downgrade status | Required backup/restore point | Observation window |
|---|---|---|---|---|---|---|
| `drop_global_cycle_index` / `remove_global_cycle_active_constraint.py` | Global `ux_cycle_single_active` index on `cycle` | Destructive policy removal; the index is intentionally not recreated | Versions using per-owner active-cycle behavior after `baseline_2026_08_26` | Prohibited as an automatic downgrade; the migration `downgrade()` is intentionally a no-op because restoring the global constraint conflicts with the per-owner model | Approved database backup immediately before upgrade; restore the backup instead of downgrading if the previous policy is required | Keep the last-known-good application and database restore point through one release cycle and verify cycle activation behavior before release closure |

This migration is not downgrade-safe. Its no-op `downgrade()` is an explicit policy
decision, not evidence that rollback has been rehearsed. A backup/restore exercise
is required before any tenant or RLS schema migration is applied on top of it.

Destructive or irreversible changes require an explicit approval record and a recovery alternative. A database downgrade is not assumed to be safe merely because an Alembic downgrade function exists.

## Rollback rehearsal baseline

The rollback rehearsal must cover the application topology documented in [runtime-entrypoint-contract.md](runtime-entrypoint-contract.md):

1. Record the current release identifiers for API, worker, BFF, and web.
2. Capture database backup or restore-point evidence.
3. Deploy a representative forward change using the supported deployment path.
4. Exercise API, worker, BFF, and web readiness and one representative user journey.
5. Restore the last-known-good application artifacts.
6. Restore or reconcile the database according to the migration safety classification.
7. Re-run readiness and the representative journey.
8. Record elapsed time, observed data loss, operator actions, and unresolved risks.

The rehearsal must state whether rollback is application-only, application-plus-database, or unavailable after a specific migration step.

The repository readiness gate is [verify_deploy_readiness.py](../scripts/verify_deploy_readiness.py). Its bounded operational invocation is:

```text
python scripts/verify_deploy_readiness.py --compose-file deploy/docker/docker-compose.yml
```

The gate exposes separate backend, BFF, and web health URLs and can skip Compose checks for an already-managed environment. It must be run against a started target when capturing release evidence; a help-screen invocation is not readiness evidence.

The rollback procedure for application, BFF, and migration changes is documented in [migration-rollback-runbook.md](migration-rollback-runbook.md). It remains documented but not rehearsed.

Operational evidence captured on 2026-08-31: the bounded gate passed against the Compose target. Postgres, backend API, worker, BFF, and web were running; backend and BFF health checks returned `ok`, and the web root returned healthy HTML. This verifies readiness only and does not replace rollback or migration rehearsal evidence.

Migration baseline captured read-only from the running backend: Alembic reports `drop_global_cycle_index (head)` on PostgreSQL and assumes transactional DDL. No forward migration candidate has been selected for rollback rehearsal yet.

## Governance gates

No architecture package may be marked `CLOSED` when any of these are unknown:

- canonical owner and dependency direction;
- supported startup and deployment profile;
- data compatibility during rollout and rollback;
- security owner for the relevant boundary;
- evidence location and verification date;
- residual risk and follow-up owner.

The status lifecycle remains:

```text
PLANNED -> IN-PROGRESS -> IMPLEMENTED -> VERIFIED -> CLOSED
```

Written intent can move a package into `IN-PROGRESS`; only acceptance evidence can move it into `VERIFIED`.

## Exit review checklist

- [ ] P0-00 inventory has verified ownership and startup topology.
- [ ] P0-01 import direction and compatibility facade path are evidenced.
- [ ] P0-02 supported runtime profiles and readiness checks are evidenced.
- [ ] P0-03 BFF responsibilities, security boundary, and performance impact are evidenced.
- [ ] P0-04 compatibility callers and removal or deprecation paths are evidenced.
- [ ] P0-05 Documentation HQ and lifecycle checks are evidenced.
- [ ] P0-06 rollback rehearsal and migration safety records are attached.
- [ ] Open risks have owners, dates, and explicit release disposition.

## Exit decision

The architecture is ready for the next SaaS planning gate only when the checklist is complete or every exception has an explicit owner-approved disposition. This document should then be updated with the review date, evidence links, and retro note before P0-06 is marked `VERIFIED` or `CLOSED`.
