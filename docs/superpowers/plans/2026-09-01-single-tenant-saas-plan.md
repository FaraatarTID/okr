# Single-Tenant Enterprise SaaS Implementation Plan

Documentation HQ: [README](../../../README.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first enterprise SaaS capability as repeatable, isolated customer environments around the existing on-premise application.

**Architecture:** Keep the current modular-monolith API, worker, BFF, and SPA contracts. Add an explicit customer-environment contract and lifecycle automation around them, with one dedicated application/database environment per enterprise. Keep the control plane limited to environment metadata and lifecycle operations, not customer-domain data.

**Tech Stack:** Python backend and worker, FastAPI/BFF, SPA frontend, PostgreSQL, Docker Compose, `just`, existing health/readiness and OpenAPI gates, provider-supported backup tooling, and deployment automation appropriate to the selected cloud target.

**Spec:** `docs/superpowers/specs/2026-09-01-single-tenant-saas-design.md`

## Global Constraints

- Preserve the supported on-premise deployment profile.
- Do not introduce tenant identifiers, shared-database RLS, or cross-customer domain schema in the pre-SaaS baseline.
- Preserve BFF security, actor binding, session revocation, authorization, worker, OpenAPI, and import-boundary invariants.
- Customer-domain traffic must not be routed through the control plane.
- Provisioning and retirement must be idempotent.
- Real customer data is prohibited until backup, restore, RPO/RTO, and application rollback evidence exists.
- Every lifecycle operation must be auditable without logging customer-domain data.

---

### Task 1: Freeze the SaaS environment contract

**Files:**
- Create: `docs/superpowers/specs/2026-09-01-single-tenant-saas-design.md` (already approved; use as the contract source)
- Create: `docs/saas/customer-environment-contract.md`
- Modify: `ENTERPRISE_SAAS_ROADMAP.md`
- Modify: `docs/architecture-status.md`
- Test: `tests/test_customer_environment_contract.py`

**Interfaces:**
- Produces a versioned environment manifest with `environment_id`, `customer_id`, `deployment_profile`, `application_version`, `database_target`, `health_endpoint`, `backup_policy`, and lifecycle state.
- Produces lifecycle states `PROVISIONING`, `READY`, `SUSPENDED`, `UPGRADING`, `DEGRADED`, and `RETIRED`.
- Produces validation that rejects missing identity, unsupported profile, empty version, or invalid state transitions.

- [ ] **Step 1: Write the failing contract tests**

```python
def test_manifest_requires_isolated_database_target():
    manifest = EnvironmentManifest(
        environment_id="env-a",
        customer_id="customer-a",
        deployment_profile="single_tenant_saas",
        application_version="release-1",
        database_target="postgres://customer-a",
    )
    assert manifest.is_isolated is True


def test_retired_environment_cannot_return_to_ready():
    assert transition(EnvironmentState.RETIRED, EnvironmentEvent.ACTIVATE) is None
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_customer_environment_contract.py -q`
Expected: FAIL because the manifest, state enum, and transition function do not yet exist.

- [ ] **Step 3: Implement the contract module**

Create `src/saas/environment_contract.py` with typed manifest validation and an explicit transition table. Reject `on_premise` manifests that claim control-plane ownership and reject `single_tenant_saas` manifests without a dedicated database target.

- [ ] **Step 4: Document the contract and update the roadmap**

Document field meanings, lifecycle transitions, idempotency keys, and operator-visible failure states in `docs/saas/customer-environment-contract.md`. Link the contract from `ENTERPRISE_SAAS_ROADMAP.md` and move Phase 0 to `IN-PROGRESS` in `docs/architecture-status.md`.

- [ ] **Step 5: Run the focused tests and record evidence**

Run: `python -m pytest tests/test_customer_environment_contract.py -q`
Expected: PASS with invalid manifests and illegal transitions rejected.

### Task 2: Add profile-safe environment configuration

**Files:**
- Create: `src/saas/environment_config.py`
- Modify: `scripts/check_deploy_config.py`
- Modify: `deploy/docker/docker-compose.yml`
- Create: `deploy/docker/.env.saas.example`
- Test: `tests/test_saas_environment_config.py`

**Interfaces:**
- Produces `SaaSEnvironmentConfig.from_env()` with explicit `deployment_profile`, `environment_id`, `customer_id`, `database_url`, `health_url`, and backup-policy settings.
- Rejects SaaS startup when the profile is missing, the environment identity is missing, or an unsupported HTTPS data fallback is selected.
- Leaves `on_premise` and existing self-hosted compatibility behavior unchanged.

- [ ] **Step 1: Write tests for valid and invalid profile combinations**

```python
def test_saas_profile_requires_environment_identity(monkeypatch):
    monkeypatch.setenv("OKR_DEPLOYMENT_PROFILE", "single_tenant_saas")
    monkeypatch.delenv("OKR_ENVIRONMENT_ID", raising=False)
    with pytest.raises(ConfigError, match="OKR_ENVIRONMENT_ID"):
        SaaSEnvironmentConfig.from_env()


def test_saas_profile_rejects_https_fallback(monkeypatch):
    monkeypatch.setenv("OKR_DEPLOYMENT_PROFILE", "single_tenant_saas")
    monkeypatch.setenv("OKR_ENVIRONMENT_ID", "env-a")
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "supabase_api")
    with pytest.raises(ConfigError, match="database"):
        SaaSEnvironmentConfig.from_env()
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_saas_environment_config.py -q`
Expected: FAIL because the SaaS configuration object and profile checks do not yet exist.

- [ ] **Step 3: Implement profile validation and configuration documentation**

Implement the typed configuration object, add the environment identity variables to `deploy/docker/.env.saas.example`, and make Compose pass them to API, worker, BFF, and web services without embedding secrets in images.

- [ ] **Step 4: Run deployment configuration checks**

Run: `python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env.saas.example`
Expected: the example configuration either passes or reports only documented local-development warnings; SaaS fallback must be rejected.

### Task 3: Build idempotent isolated-environment provisioning

**Files:**
- Create: `src/saas/provisioning.py`
- Create: `scripts/provision_saas_environment.py`
- Create: `tests/test_saas_provisioning.py`
- Modify: `justfile`
- Modify: `docs/launcher-command-matrix.md`

**Interfaces:**
- `Provisioner.provision(manifest) -> ProvisionResult`
- `Provisioner.suspend(environment_id) -> LifecycleResult`
- `Provisioner.retire(environment_id) -> LifecycleResult`
- `Provisioner.provision()` is idempotent for the same `environment_id` and refuses conflicting customer/database identities.

- [ ] **Step 1: Write tests for idempotency and isolation**

```python
def test_repeating_provision_returns_existing_environment(fake_provider):
    first = Provisioner(fake_provider).provision(manifest("env-a", "customer-a"))
    second = Provisioner(fake_provider).provision(manifest("env-a", "customer-a"))
    assert second.environment_id == first.environment_id
    assert fake_provider.create_calls == 1


def test_conflicting_identity_is_rejected(fake_provider):
    provisioner = Provisioner(fake_provider)
    provisioner.provision(manifest("env-a", "customer-a"))
    with pytest.raises(ProvisioningConflict):
        provisioner.provision(manifest("env-a", "customer-b"))
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_saas_provisioning.py -q`
Expected: FAIL because the provider adapter and provisioner do not yet exist.

- [ ] **Step 3: Implement provider-neutral provisioning ports and adapters**

Define provider interfaces for application runtime, database, secrets, DNS/routing metadata, and health registration. Implement a local disposable adapter first so the complete lifecycle can be exercised without cloud credentials.

- [ ] **Step 4: Implement the command-line lifecycle operations**

Make `scripts/provision_saas_environment.py` support `provision`, `suspend`, and `retire`, accept a manifest path, emit an idempotency result, and write no customer-domain records.

- [ ] **Step 5: Add canonical task commands and run focused tests**

Add `just saas-provision MANIFEST=... CREDENTIAL_FILE=...`, `just saas-suspend ENVIRONMENT_ID=... CREDENTIAL_FILE=...`, and `just saas-retire ENVIRONMENT_ID=... CREDENTIAL_FILE=...`. Resolve the operator from `OKR_OPERATOR_TOKEN` against the credential file. Run: `python -m pytest tests/test_saas_provisioning.py -q`. Expected: PASS.

### Task 4: Add versioned deployment and application rollback

**Files:**
- Create: `src/saas/release_operations.py`
- Create: `scripts/deploy_saas_release.py`
- Create: `tests/test_saas_release_operations.py`
- Modify: `deploy/docker/docker-compose.yml`
- Modify: `docs/migration-rollback-runbook.md`

**Interfaces:**
- `ReleaseManager.deploy(environment_id, release_artifact) -> DeploymentResult`
- `ReleaseManager.rollback(environment_id, previous_artifact) -> DeploymentResult`
- Deployment records `previous_version`, `target_version`, health outcome, operator identity, and rollback result.
- Rollback refuses an artifact that is not immutable or not registered for the environment.

- [ ] **Step 1: Write tests for health-gated promotion and rollback**

```python
def test_unhealthy_release_returns_to_previous_artifact(fake_runtime):
    manager = ReleaseManager(fake_runtime)
    result = manager.deploy("env-a", artifact("release-2", healthy=False))
    assert result.status == "ROLLED_BACK"
    assert fake_runtime.active_version("env-a") == "release-1"


def test_rollback_records_operator_and_versions(fake_runtime):
    result = ReleaseManager(fake_runtime).rollback("env-a", artifact("release-1"))
    assert result.previous_version == "release-2"
    assert result.target_version == "release-1"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_saas_release_operations.py -q`
Expected: FAIL because release registration, health gates, and rollback operations do not yet exist.

- [ ] **Step 3: Implement immutable artifact registration and deployment records**

Store artifact digest, environment, operator, and deployment state. Run readiness checks before marking a release active. On failure, restore the previous application artifact without restoring the database.

- [ ] **Step 4: Exercise rollback with two real local artifacts**

Build or obtain two versioned backend/BFF/web artifact sets, deploy the first to an isolated environment, promote the second, force a health failure, and execute the rollback command. Preserve the deployment record and evidence in the rollback runbook.

- [ ] **Step 5: Run focused release tests**

Run: `python -m pytest tests/test_saas_release_operations.py -q`
Expected: PASS, including failed-release rollback and successful explicit rollback.

### Task 5: Implement production backup and restore operations

**Files:**
- Create: `src/saas/backup_operations.py`
- Create: `scripts/backup_saas_environment.py`
- Create: `scripts/restore_saas_environment.py`
- Create: `tests/test_saas_backup_operations.py`
- Modify: `docs/migration-rollback-runbook.md`
- Modify: `docs/architecture-status.md`

**Interfaces:**
- `BackupManager.create(environment_id) -> BackupRecord`
- `BackupManager.verify(backup_id) -> VerificationResult`
- `RestoreManager.restore(backup_id, isolated_target) -> RestoreRecord`
- Records provider, timestamp, retention class, checksum/verification result, RPO/RTO measurements, and operator identity.

- [ ] **Step 1: Write tests for backup freshness and isolated restore**

```python
def test_backup_record_requires_provider_and_checksum():
    with pytest.raises(ValueError):
        BackupRecord(environment_id="env-a", provider="", checksum="")


def test_restore_never_targets_live_environment(fake_provider):
    with pytest.raises(UnsafeRestoreTarget):
        RestoreManager(fake_provider).restore("backup-a", isolated_target=False)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_saas_backup_operations.py -q`
Expected: FAIL because backup records, provider integration, and restore safety checks do not yet exist.

- [ ] **Step 3: Implement provider-backed backup and isolated restore ports**

Require provider-supported backup identifiers, never use application table dumps as the production mechanism, reject live restore targets by default, and calculate measured restore duration for RTO evidence.

- [ ] **Step 4: Add retention and freshness monitoring**

Expose backup age, last successful backup, failed backup state, and restore-test state to the control-plane metadata contract without exposing customer data.

- [ ] **Step 5: Run focused tests and record an isolated restore drill**

Run: `python -m pytest tests/test_saas_backup_operations.py -q`
Expected: PASS. Record the provider, backup identifier, isolated target, elapsed restore time, and cleanup result in `docs/migration-rollback-runbook.md`.

### Task 6: Add control-plane environment inventory and lifecycle audit

**Files:**
- Create: `src/saas/control_plane.py`
- Create: `backend_app/routers/control_plane_routes.py`
- Create: `tests/test_control_plane_environment_routes.py`
- Modify: `backend_app/main.py`
- Modify: `docs/bff-boundary-adr.md`
- Modify: `docs/architecture-status.md`

**Interfaces:**
- `ControlPlane.list_environments() -> list[EnvironmentSummary]`
- `ControlPlane.get_environment(environment_id) -> EnvironmentSummary`
- `ControlPlane.record_lifecycle_event(event) -> AuditEvent`
- Control-plane routes manage environment metadata only and cannot read or mutate customer OKR records.

- [ ] **Step 1: Write route and boundary tests**

```python
def test_control_plane_lists_metadata_without_domain_records(client):
    response = client.get("/control-plane/environments", headers=operator_headers())
    assert response.status_code == 200
    assert "goals" not in response.json()


def test_customer_session_cannot_use_control_plane(client):
    response = client.get("/control-plane/environments", headers=customer_headers())
    assert response.status_code in {401, 403}
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_control_plane_environment_routes.py -q`
Expected: FAIL because control-plane inventory and operator authorization do not yet exist.

- [ ] **Step 3: Implement metadata-only control-plane service and routes**

Use separate operator authorization, return environment identity/version/health/backup state, and keep customer-domain repositories unreachable from the control-plane module.

- [ ] **Step 4: Add import and route boundary checks**

Extend the existing import-boundary and BFF allowlist checks so control-plane modules cannot import customer-domain read/write helpers and customer sessions cannot access operator routes.

- [ ] **Step 5: Run focused and existing boundary tests**

Run: `python -m pytest tests/test_control_plane_environment_routes.py tests/test_facade_service_boundary.py -q`
Expected: PASS.

### Task 7: Complete SaaS entry-gate evidence and handoff

**Files:**
- Modify: `ENTERPRISE_SAAS_ROADMAP.md`
- Modify: `docs/architecture-status.md`
- Modify: `docs/migration-rollback-runbook.md`
- Modify: `docs/WORKLOG.md`
- Create: `docs/saas/phase-1-entry-evidence.md`

**Interfaces:**
- Evidence bundle identifies the promoted release artifacts, environment, health checks, provisioning result, rollback rehearsal, backup/restore drill, RPO/RTO, and named owners.
- Phase status may advance only when every required evidence item is present.

- [ ] **Step 1: Assemble the evidence checklist**

Record artifact digests, environment identifier, provisioning idempotency result, health result, rollback result, backup identifier, restore result, RPO/RTO, and reviewers in `docs/saas/phase-1-entry-evidence.md`.

- [ ] **Step 2: Run the complete SaaS-focused gate**

Run: `just check`, `python scripts/check_deploy_config.py --mode runtime --env-file <approved-saas-env>`, `python scripts/check_import_boundaries.py`, and the focused SaaS test suite. Expected: all required checks pass and no tenant/RLS work is implied.

- [ ] **Step 3: Update lifecycle status and retrospective**

Move only evidenced roadmap items to `VERIFIED` or `CLOSED`, record the reviewer and one-line retrospective, and leave deferred shared-database/RLS work explicitly deferred.

- [ ] **Step 4: Handoff to operations**

Name the operational owner, link the runbook, identify the rollback artifact pair, and record the trigger that reopens the deferred RLS/shared-database decision.
# Final whole-plan integration fix wave

The implementation must not claim production readiness until the following
cross-task controls are complete and executable: durable control-plane state
is the shared metadata boundary; authenticated principals, not raw actor
headers, authorize and audit operator actions; database metadata is an opaque
resource identifier; provisioning is concurrency-safe and preserves orphan
cleanup records; release and backup operations reconcile summaries; profiles
are `on_premise`, `single_tenant_saas`, or external `control_plane`; and
`just saas-evidence` passes with provider-backed evidence and named owners.
Shared-database RLS, tenant schema, billing, real provider selection, and
real-data onboarding remain deferred.
