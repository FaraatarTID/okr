# Operating Model Decision and Release Gates

Documentation HQ: [README](../README.md)

Status: ACTIVE DECISION RECORD

## Decision statement

The default supported runtime model is:

browser -> BFF -> backend API -> worker

The backend owns business logic and persistence behavior. The BFF owns browser-facing trust, routing, session mediation, and request shaping only. The worker remains operationally independent. Tenant isolation is explicit and environment-scoped.

This is the default contract unless a formal evidence-based exception is approved.

## Scope and intent

This decision record is intended to prevent a common but dangerous failure mode: treating a repo or a convenience deployment pattern as the architecture itself.

The repository is evidence for the operating model. It is not the authority on the real runtime contract.

## Default topology and ownership

### Supported default

- browser -> BFF -> backend API -> worker
- backend API is the authoritative application service layer
- BFF is a browser-facing mediation boundary
- worker is separate and independently diagnosable
- tenant isolation is explicit and environment-scoped

### In-scope ownership

- BFF owns: browser trust, session mediation, request validation, route allowlisting, request shaping, browser-facing observability, and security mediation near the edge.
- Backend owns: business logic, persistence behavior, service orchestration, migrations, application use cases, and domain rules.
- Worker owns: background execution and operational tasks that are not part of the browser-facing request path.

### Explicit non-ownership

The BFF must not own:
- domain business rules
- persistence access
- database connectivity
- direct migration logic
- backend domain ownership
- duplicated business semantics

The backend must not expose a direct browser-to-API default route that bypasses the trust boundary unless a specific exception is approved.

## Risk register

| Risk | Impact | Likelihood | Owner | Mitigation | No-go trigger |
|---|---|---:|---|---|---|
| Tenant data drift or partial migration | Critical | Medium | Platform/Ops | Verified inventory, explicit migration states, rollback path, dry-run, per-tenant reporting | Migration proceeds without verified inventory and rollback criteria |
| BFF security boundary weakened | Critical | Medium | Security + Architecture | Explicit BFF responsibilities, no direct DB access, no duplicate business logic, security parity evidence | Any BFF simplification or co-location without security parity evidence |
| Topology simplification by convenience | High | High | Engineering lead | Require evidence gate; no latency-only decisions | Any topology change without SLO, rollback, and failure-isolation evidence |
| Repo checks mistaken for production proof | Medium | High | Engineering lead | Treat repo as evidence layer, not source of truth | Architecture claim without runtime evidence |

## Approval gates

### Gate A: tenancy and migration gate

This gate must pass before any migration rollout.

- Each tenant has a unique environment identity.
- Each environment has an opaque database resource id.
- No credential-bearing URL is stored in metadata.
- Inventory is authoritative and verified before migration.
- Migration states are explicit and documented.
- Dry-run behavior is proven.
- Retry and fail-fast behavior are explicit.
- Rollback trigger and recovery path are defined before production.
- Per-tenant success/failure evidence is captured.

### Gate B: BFF trust gate

This gate must pass before any BFF simplification or co-location exception.

- Browser-facing trust responsibilities are explicit.
- The BFF does not own business logic or persistence.
- The BFF does not duplicate backend domain decisions.
- Security parity evidence exists.
- Failure-isolation evidence exists.
- Rollback path exists for the proposed topology.

### Gate C: deployment evidence gate

This gate must pass before any topology change.

- SLO comparison evidence is collected.
- Resource overhead evidence is captured.
- Failure-isolation evidence is reviewed.
- Security parity evidence is reviewed.
- Rollback rehearsal evidence is reviewed.
- The evidence package is linked to the release record and signoff.

## Execution sequence

1. Freeze the operating contract.
2. Define the tenancy and migration lifecycle.
3. Define the BFF trust boundary.
4. Collect evidence for topology comparison.
5. Validate against the no-go criteria.
6. Approve only the supported deployment profile.

## Required lifecycle states for migration

The migration lifecycle must be explicit and auditable:

- discovered
- preflight valid
- dry-run passed
- migration started
- verified
- complete
- rollback required
- rollback complete
- drift detected

## No-go triggers

Stop and escalate if any of the following are true:

- no verified tenant inventory exists
- no rollback criterion is defined
- a direct browser-to-backend route is introduced without approval
- the BFF boundary is blurred without evidence
- migration success is based only on exit code and not per-tenant verification
- topology change is justified by latency alone
- repo checks are treated as architecture proof instead of runtime evidence

## Owner model

### Architecture owner
Owns the default topology, ownership model, and exception process.

### Platform/Ops owner
Owns tenant inventory, migration safety, rollback criteria, and fail-fast policies.

### Security owner
Owns BFF security review and the trust-boundary decision.

### Engineering lead
Owns overall no-go authority and release signoff.

## Evidence and repo alignment

The repository remains useful and important, but it is the evidence layer, not the source of truth.

Relevant controls include:

- [justfile](../justfile)
- [scripts/check_generated_artifacts.py](../scripts/check_generated_artifacts.py)
- [scripts/check_import_boundaries.py](../scripts/check_import_boundaries.py)
- [scripts/check_deployment_topology.py](../scripts/check_deployment_topology.py)
- [scripts/migrate_tenant_databases.py](../scripts/migrate_tenant_databases.py)

These controls enforce the agreed model but do not replace the runtime and operational evidence required for a release.

## Success definition

This decision record is successful when:

- the default topology is explicit and defensible
- tenant migration is a governed state machine
- BFF responsibilities are narrow and explicit
- evidence is required before topology change
- repo enforcement supports the real runtime model instead of replacing it

## References

- [architecture-boundaries.md](architecture-boundaries.md)
- [bff-boundary-adr.md](bff-boundary-adr.md)
- [README.md](../README.md)
- [environment_contract.py](../src/saas/environment_contract.py)
- [provisioning.py](../src/saas/provisioning.py)
- [migrate_tenant_databases.py](../scripts/migrate_tenant_databases.py)
