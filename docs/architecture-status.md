# Architecture Status Ledger

Documentation HQ: [README](../README.md)

| Item | Status | Evidence | Verified | Retro note |
|---|---|---|---|---|
| P0-00 - Architecture inventory and target topology | IN-PROGRESS | [pre-saas-architecture-inventory.md](pre-saas-architecture-inventory.md) | not yet | Initial runtime inventory captured; canonical boundaries remain open for P0-01. |
| P0-01 - Canonical backend package and facade boundary | IN-PROGRESS | [architecture-boundaries.md](architecture-boundaries.md); canonical serializers, bucket, selector, bootstrap delegation, keyed/unkeyed snapshot-cache factories, all facade snapshot-cache wiring, and duplicate implementation removal completed; 29 combined boundary/cache tests passed; consolidated gate passed | partial | Snapshot behavior is verified; selector/bootstrap caller inventory, full boundary verification, and package closure remain. |
| P0-02 - Runtime and deployment entrypoint canonicalization | IN-PROGRESS | [runtime-entrypoint-contract.md](runtime-entrypoint-contract.md); runtime matrix, compatibility readiness gate, isolated SaaS `database` readiness smoke, and live compatibility health payload passed | partial | SaaS API profile smoke verified; full SaaS topology and local/Kubernetes reconciliation remain. |
| P0-03 - BFF responsibility and topology ADR | IN-PROGRESS | [bff-boundary-adr.md](bff-boundary-adr.md); [bff-security-review.md](bff-security-review.md); allowlist passed for 44 routes; BFF suite passed 65 tests; consolidated gate passed | partial | Repository security controls reviewed; production secret, rate-limit, tenant-context, and rollback evidence remain. |
| P0-04 - Root script and compatibility surface cleanup | IN-PROGRESS | [compatibility-surface-cleanup.md](compatibility-surface-cleanup.md); [compatibility-callers.md](compatibility-callers.md); [launcher-command-matrix.md](launcher-command-matrix.md); canonical cache migration, platform/login/response-scope migration, cycle/weekly-plan caller migration, explicit user serializer dependency seam, no-root-facade-import guard, and read-only Docker wrapper status path completed; 14 parity/ritual tests and 2 launcher contract tests passed; bounded Compose health captured | partial | Full wrapper start/stop rehearsal, launcher cleanup, and retirement of the parity override remain. |
| P0-05 - Documentation consolidation and lifecycle control | VERIFIED | [documentation-lifecycle-control.md](documentation-lifecycle-control.md); `python scripts/check_docs_hq_links.py` passed across 76 Markdown files after the signed-review regression repair | 2026-09-01 | Documentation control re-verified after REV-002; future ADRs must preserve the same ledger and link discipline. |
| P0-06 - Governance, migration safety, and exit review | IN-PROGRESS | [governance-migration-exit-review.md](governance-migration-exit-review.md); [migration-rollback-runbook.md](migration-rollback-runbook.md); separate provider backup/restore contracts, computed SHA-256 verification, complete persisted success/failure status, pre-registered restore-target enforcement, measured isolated restore drill, and focused backup test passed | partial | Local adapter is test-only; production provider selection, production restore evidence, and application rollback remain gated by explicit owner risk acceptance for disposable pre-SaaS. |
| SaaS Phase 0 - Environment contract | IN-PROGRESS | [customer-environment-contract.md](saas/customer-environment-contract.md); typed `EnvironmentManifest`, explicit lifecycle transition table, isolated database-target validation, and retired-state rejection tests | 2026-09-01 | Contract frozen for the single-tenant SaaS path; provisioning, control plane, tenancy, RLS, and migrations remain out of scope. |
## Signed review follow-up: 2026-09-01

The runtime compatibility database is confirmed at `drop_global_cycle_index (head)`. A PostgreSQL 17-compatible backup of the live runtime database was restored successfully into an isolated rehearsal instance. P0-06 remains open only for application release rollback rehearsal and selection of a prior deployable application artifact; tenant/RLS schema work must not start until that remaining condition is evidenced.
## Owner decision: disposable pre-SaaS database - 2026-09-01

The runtime database has been intentionally emptied for pre-SaaS work. Application tables were truncated with cascade, the schema was retained, and no migration or dump workflow is required. Database recovery controls are deferred to the SaaS persistence phase; this does not authorize tenant/RLS work yet.
## Owner confirmation: branch promotion - 2026-09-01

The reviewed `SPA-BFF-clean` work has been promoted to the project mainline. REV-001 is resolved by owner confirmation. The promoted baseline is intentionally empty of application data and remains pre-SaaS; tenant/RLS work is still deferred.
## Active handoff: pre-SaaS product baseline

The project is ready for pre-SaaS product work on the promoted mainline. The runtime database is intentionally empty. Tenant isolation, RLS, and durable SaaS persistence remain explicit future-phase work and must not be introduced implicitly through feature implementation.
## Decision: architecture initiative handoff - 2026-09-01

The pre-SaaS architecture work is complete for its current scope and is handed off to product implementation. Further architecture changes require a concrete product requirement or an explicitly scheduled SaaS transition; speculative tenant, RLS, migration, and persistence work is out of scope.
## P0-06 disposition: deferred by explicit owner risk acceptance - 2026-09-01

P0-06 is deferred for the disposable pre-SaaS phase by explicit owner risk acceptance. This is not a claim that production rollback controls are complete. The SaaS persistence entry gate must require provider-supported backup/recovery, isolated restore evidence, application rollback rehearsal, documented RPO/RTO, and an accountable operational owner before real tenant data is introduced.

## Task 5 evidence: provider-backed backup and restore operations - 2026-09-01

Task 5 is implemented without touching the live database. `BackupManager` and
`RestoreManager` use provider-issued identifiers and checksum metadata; the
local rehearsal adapter does not create application table dumps. Restore rejects
live targets before provider invocation and records operator, target, checksum
verification, and measured duration. The focused test command returned
`18 passed in 0.36s`. Backup create, verification, and restore failure states persist complete
operational metadata across manager and CLI reload. The local adapter requires explicit `--test-only`, while
the production CLI refuses to run until a real provider is configured. This
closes the implementation slice while leaving the production-provider and
production-disaster-recovery gate open as intended.

## Task 6 evidence: control-plane environment inventory and lifecycle audit - 2026-09-01

The control plane is metadata-only. Operator-authorized routes expose environment
identity, deployment profile, application version, health, database, release, and
backup metadata and record lifecycle audit events without reading or mutating
customer OKR records. Import and route boundary tests cover the separation. No
customer-domain proxying, tenant schema, RLS, migrations, or live cloud operations
are introduced by this task.

## 2026-09-01 - Task 7 Phase 1 entry-gate evidence

Task 1-6 evidence has been consolidated in [Phase 1 entry evidence](saas/phase-1-entry-evidence.md). The result is **evidence assembled, Phase 1 promotion blocked**.

- The single-tenant environment contract, profile-safe configuration, idempotent provisioning, versioned release operations, backup/restore contracts, and metadata-only control-plane inventory have focused local evidence.
- Final reported focused evidence counts are: Task 1 `22 passed`; Task 2 `27 passed`; Task 3 `14 passed`; Task 4 `13 passed`; Task 5 `18 passed`; Task 6 `34 passed` for the paired control-plane/boundary evidence.
- Provider-backed application rollback: **NOT AVAILABLE - provider/artifact not selected**.
- Provider backup, restore, measured restore timing, retention/freshness monitoring, and production RPO/RTO: **NOT AVAILABLE - provider/artifact not selected**.
- Platform/operations owner: **UNASSIGNED**.
- Real customer data remains prohibited until those provider-specific gates and application rollback evidence are complete.
- Shared-database RLS, tenant identifiers, and real-data onboarding remain deferred.

The phase evidence checker is executable via `just saas-evidence` and is
structured: it parses the fenced JSON evidence object and validates provider
backup identity, immutable artifact digests, rollback result, measured RPO/RTO,
and named owners rather than trusting headings or prose. It is expected to fail
while provider evidence or the named operations owner is absent. Control-plane state is durable by default at
`tmp/saas-control-plane.json`; provisioning, release, and backup operations
reconcile their metadata into that same state boundary.

## 2026-09-01 - Final blocker fix wave

The whole-plan integration blockers are addressed locally: provisioning and
control-plane persistence use one bounded crash-safe lock without deleting the
lock path; provider-returned canonical database resource IDs are persisted;
failed release and backup/restore operations reconcile degraded/failed state;
provisioning and release CLI operations require an explicit operator and record
lifecycle audit events; and control-plane read/write operations reload under
the lock so concurrent processes preserve records and events. These are local
implementation controls only. Provider-backed backup/restore, provider-backed
rollback, measured production RPO/RTO, and named operations ownership remain
intentionally blocking gates for production SaaS and real customer data.

## 2026-09-01 - Whole-plan review remediation

The evidence checker now requires a machine-readable production attestation
with provider provenance, provider-issued backup/restore identifiers, pinned
artifact digests, numeric measured rollback/RPO/RTO values, named owners, and
an HMAC-SHA256 signature verified with the configured attestation secret. The
attested values are cross-bound to the structured evidence fields. Current
evidence fails closed because those facts and the configured signature are
unavailable. Provisioning, release, backup, and restore CLIs now resolve
an authenticated principal from `OKR_OPERATOR_TOKEN` plus a credential file;
arbitrary `--operator` values and insecure defaults are rejected. Release and
backup local state persistence uses the shared crash-safe lock, and provider
database resource IDs are strictly opaque and canonical. Production SaaS and
real-data onboarding remain blocked.

## 2026-09-01 - Final trust-boundary hardening wave

Lifecycle service APIs now require an `OperatorCredential` object carrying the
authenticated principal and credential provenance; arbitrary operator strings
are rejected. The credential-file/token resolver constructs this object for
CLIs, and audit records preserve only its authenticated principal. Control-plane
initialization writes execute inside the shared crash-safe guard. No live
provider was invoked and tenant/RLS/customer-domain behavior is unchanged.
