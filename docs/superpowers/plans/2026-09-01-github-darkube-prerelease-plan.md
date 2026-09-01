# GitHub -> Darkube Disposable Pre-Release Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a disposable, synthetic-data pre-release environment that gates a protected GitHub `pre-release` branch with GitHub Actions and deploys four separate application apps plus private PostgreSQL through Darkube GitHub integration.

**Architecture:** GitHub is the source of truth and quality gate. Darkube’s GitHub integration watches the protected `pre-release` branch and hosts `spa-web`, `spa-bff`, `backend-api`, and `backend-worker` in namespace `okr-pre-release`; a disposable private PostgreSQL database supplies the schema. Provider-specific setup is documented and manually verified because no public Hamravesh provisioning/deployment API is established.

**Tech Stack:** GitHub Actions, Python 3.11, Node.js 22, Docker, existing FastAPI backend, existing Fastify BFF, existing Next.js web, PostgreSQL 16 baseline, Alembic, Darkube GitHub integration, Hamravesh managed PostgreSQL where available, existing readiness/SLO/Playwright tooling.

**Spec:** `docs/superpowers/specs/2026-09-01-github-darkube-prerelease-design.md`

## Global Constraints

- The deployment branch is `pre-release` and is protected against direct pushes.
- The Darkube namespace/project is `okr-pre-release` and is disposable.
- The deployed applications are `okr-prerelease-web`, `okr-prerelease-bff`, `okr-prerelease-api`, and `okr-prerelease-worker`.
- Only synthetic data and non-production secrets may enter the environment.
- The database has private connectivity and no public access.
- GitHub Actions does not receive production credentials or unrestricted Hamravesh credentials.
- The API and worker use the same backend build input and commit; all four apps use the same commit.
- Release identity is Git commit SHA plus provider build/deployment IDs; `latest` is not a release identity.
- `OKR_DEPLOYMENT_PROFILE=single_tenant_saas`, `OKR_SAAS_MODE=true`, and `OKR_DATA_ACCESS_MODE=database` are required for the pre-release runtime.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_ANON_KEY` remain empty in the SaaS profile.
- The pre-release database is disposable; schema setup uses one controlled Alembic head migration and never a production database.
- No tenant schema, shared-database RLS, customer provisioning, or production SaaS evidence closure is part of this plan.
- Darkube provider automation is not invented; unsupported provider behavior stops at a documented confirmation gate.

---

## File map

### Files to create

- `.github/workflows/darkube-prerelease.yml`: protected-branch quality, four-image build, and post-deployment verification workflow.
- `deploy/darkube/prerelease/README.md`: exact Darkube console setup, component values, networking checks, reset, and rollback procedure.
- `deploy/darkube/prerelease/.env.example`: non-secret runtime key contract with synthetic examples and no usable credentials.
- `scripts/verify_prerelease_config.py`: pre-release-specific validation layered on the existing deployment config validator.
- `scripts/verify_prerelease_smoke.py`: reachable web/BFF/API smoke checks plus worker/database evidence inputs.
- `scripts/write_prerelease_evidence.py`: sanitized machine-readable evidence writer with secret-value rejection.
- `tests/test_prerelease_config.py`: configuration and security regression tests.
- `tests/test_prerelease_workflow_contract.py`: workflow permissions, branch, and component coverage tests.
- `tests/test_prerelease_build.py`: four-component Docker build contract tests.
- `tests/test_prerelease_smoke.py`: offline smoke/evidence parsing tests and mocked failure behavior.
- `tests/test_prerelease_evidence.py`: evidence schema, secret rejection, and rollback identity tests.
- `docs/saas/prerelease-evidence.md`: checked-in evidence template and latest operator-recorded pre-release result.
- `docs/saas/prerelease-runbook.md`: operator runbook for initial setup, migration, verification, reset, logs, and redeployment.

### Files to modify

- `.github/workflows/ci.yml`: include `pre-release` in the existing branch coverage only if the dedicated workflow cannot reuse the current checks without duplication.
- `scripts/check_deploy_config.py`: expose reusable validation behavior without weakening existing on-premise or SaaS fail-closed rules.
- `scripts/verify_deploy_readiness.py`: add only the smallest provider-neutral option needed to verify non-local URLs or worker evidence; preserve existing Compose behavior.
- `scripts/verify_e2e_environment.py`: accept the pre-release public URL through an explicit environment variable without changing local defaults.
- `scripts/slo_probe.py`: accept the pre-release public probe target and emit CI-readable output if the current interface cannot do so.
- `docs/architecture-status.md`: record implementation evidence, provider confirmations, and any blocked Hamravesh capability.
- `docs/launcher-command-matrix.md`: add the documented GitHub/Darkube pre-release operator journey without presenting it as a local launcher.
- `docs/saas/phase-1-entry-evidence.md`: link the pre-release result while preserving the production-provider and operations-owner gate.

## Interfaces shared across tasks

The implementation must use these stable interfaces:

```python
def validate_prerelease_env(env: Mapping[str, str]) -> ValidationReport: ...

def verify_prerelease_smoke(
    *,
    web_url: str,
    bff_health_url: str,
    api_health_url: str,
    timeout_seconds: float = 10.0,
) -> PreReleaseSmokeResult: ...

def write_prerelease_evidence(
    evidence: PreReleaseEvidence,
    destination: Path,
) -> None: ...
```

`PreReleaseEvidence` must contain `environment`, `source_ref`, `commit_sha`, `darkube_namespace`, four build IDs, opaque database resource ID, migration head, health result, smoke result, rollback result, operator, and UTC timestamp. It must reject connection URLs, passwords, tokens, and values containing the repository placeholder markers.

## Task 1: Freeze the pre-release contract and provider confirmation checklist

**Files:**
- Create: `deploy/darkube/prerelease/README.md`
- Create: `deploy/darkube/prerelease/.env.example`
- Create: `docs/saas/prerelease-runbook.md`
- Test: `tests/test_prerelease_config.py`

**Interfaces:**
- Consumes: the environment keys documented in `docs/superpowers/specs/2026-09-01-github-darkube-prerelease-design.md` and `deploy/docker/.env.saas.example`.
- Produces: the exact component names, commands, ports, env-key contract, namespace, private networking requirements, and provider confirmation checklist consumed by Tasks 2-8.

- [ ] **Step 1: Write contract tests for names and forbidden configuration**

```python
def test_prerelease_contract_uses_dedicated_names():
    assert prerelease_namespace() == "okr-pre-release"
    assert application_names() == {
        "web": "okr-prerelease-web",
        "bff": "okr-prerelease-bff",
        "api": "okr-prerelease-api",
        "worker": "okr-prerelease-worker",
    }

def test_prerelease_contract_rejects_production_markers():
    report = validate_prerelease_env({"OKR_CUSTOMER_ID": "production"})
    assert not report.ok
```

- [ ] **Step 2: Run the focused test to verify the contract is absent**

Run: `python -m pytest tests/test_prerelease_config.py -q`

Expected: FAIL because the pre-release contract module and validator do not exist.

- [ ] **Step 3: Write the exact Darkube setup documentation and non-secret env template**

Document the four app source paths/Dockerfiles/commands, the database attachment, private address requirement, public ingress rules, required runtime keys, synthetic reset procedure, log locations, and the eight provider confirmation gates. Use `CHANGE_ME` only in the template, never in evidence or executable runtime material.

- [ ] **Step 4: Implement the smallest contract helpers and validator**

Implement `prerelease_namespace()`, `application_names()`, and `validate_prerelease_env()` as provider-neutral helpers. Reject production-like environment/customer identifiers, public database URLs, non-SaaS profiles, enabled Supabase fallback, missing secure flags, and placeholder runtime secrets.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_prerelease_config.py -q`

Expected: PASS with coverage for valid synthetic configuration, missing values, public database URL, production markers, and forbidden Supabase fallback.

- [ ] **Step 6: Commit**

```bash
git add deploy/darkube/prerelease docs/saas/prerelease-runbook.md tests/test_prerelease_config.py
git commit -m "docs: define disposable Darkube prerelease contract"
```

## Task 2: Add the protected-branch GitHub quality workflow

**Files:**
- Create: `.github/workflows/darkube-prerelease.yml`
- Modify: `.github/workflows/ci.yml` only if the branch coverage decision in the file map requires it.
- Test: `tests/test_prerelease_workflow_contract.py`

**Interfaces:**
- Consumes: GitHub pull request/push events for `pre-release`, Task 1 config validator, existing repository gates in `ci.yml`.
- Produces: required check names, read-only permissions, build coverage for web/BFF/API/worker, and a post-deploy workflow-dispatch verification path.

- [ ] **Step 1: Write workflow contract tests**

```python
def test_prerelease_workflow_is_protected_and_builds_all_components():
    workflow = load_yaml(Path(".github/workflows/darkube-prerelease.yml"))
    assert workflow["permissions"] == {"contents": "read"}
    text = Path(".github/workflows/darkube-prerelease.yml").read_text()
    for marker in ("spa-web/Dockerfile", "spa-bff/Dockerfile", "deploy/docker/Dockerfile", "backend-worker"):
        assert marker in text

def test_workflow_never_uses_production_secrets_or_ssh_deploy():
    text = Path(".github/workflows/darkube-prerelease.yml").read_text().lower()
    assert "ssh_key" not in text
    assert "production" not in text
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `python -m pytest tests/test_prerelease_workflow_contract.py -q`

Expected: FAIL because the dedicated workflow and test do not exist.

- [ ] **Step 3: Implement the workflow quality stages**

Create jobs for validation, backend tests, SPA/BFF tests, dependency/security checks, migration lint, and Docker build checks. The Docker checks must build the three Dockerfiles and verify both backend commands using the same backend build context. Use `needs:` so the final required job cannot pass when an earlier job fails.

The workflow may verify a deployed target only on `workflow_dispatch`, using `DARKUBE_PRERELEASE_WEB_URL`, `DARKUBE_PRERELEASE_BFF_HEALTH_URL`, and `DARKUBE_PRERELEASE_API_HEALTH_URL` as non-production environment-scoped values. It must not attempt to call an undocumented Hamravesh API.

- [ ] **Step 4: Configure branch protection documentation**

Document that pull requests into `pre-release` require the dedicated workflow’s validation, test, security, and build checks. Direct pushes and force pushes are disabled. Darkube watches the merged branch, not an unreviewed feature branch.

- [ ] **Step 5: Run contract and YAML checks**

Run: `python -m pytest tests/test_prerelease_workflow_contract.py -q`

Expected: PASS; additionally parse the workflow with the repository’s available YAML checker or GitHub Actions workflow syntax check.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/darkube-prerelease.yml .github/workflows/ci.yml tests/test_prerelease_workflow_contract.py
git commit -m "ci: gate the Darkube prerelease branch"
```

## Task 3: Add four-container build and release identity checks

**Files:**
- Modify: `.github/workflows/darkube-prerelease.yml`
- Create: `scripts/check_prerelease_build.py`
- Create: `tests/test_prerelease_build.py`

**Interfaces:**
- Consumes: GitHub commit SHA, Dockerfiles, and the four process commands.
- Produces: a build-contract result and a release identity containing commit SHA and component labels, without pushing images or using `latest`.

- [ ] **Step 1: Write build contract tests**

```python
def test_build_contract_covers_api_and_worker_from_backend_dockerfile():
    result = check_build_contract(Path("."))
    assert result.components["api"].dockerfile == "deploy/docker/Dockerfile"
    assert result.components["worker"].command == "python -m backend_app.worker"

def test_build_contract_rejects_latest_as_release_identity():
    with pytest.raises(ValueError, match="latest"):
        release_identity(commit_sha="latest", build_ids={})
```

- [ ] **Step 2: Run focused tests and observe the missing implementation**

Run: `python -m pytest tests/test_prerelease_build.py -q`

Expected: FAIL because the build contract module does not exist.

- [ ] **Step 3: Implement build-contract validation**

Validate that web, BFF, API, and worker entries point to the expected Dockerfiles/commands and that the release identity is the 40-character Git SHA. Do not add registry publication or provider deployment logic.

- [ ] **Step 4: Add workflow build checks**

Build `spa-web`, `spa-bff`, and backend images with Docker using commit-scoped local tags such as `okr-prerelease-backend:${GITHUB_SHA}`. Run a second backend container-contract check for the worker command. Do not use `docker compose up --build` as a proxy for four independent Darkube apps.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_prerelease_build.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/darkube-prerelease.yml scripts/check_prerelease_build.py tests/test_prerelease_build.py
git commit -m "ci: verify prerelease component builds"
```

## Task 4: Implement remote health and smoke verification

**Files:**
- Create: `scripts/verify_prerelease_smoke.py`
- Modify: `scripts/verify_deploy_readiness.py` only if a provider-neutral remote URL mode is required.
- Modify: `scripts/verify_e2e_environment.py` only to accept an explicit pre-release target.
- Create: `tests/test_prerelease_smoke.py`

**Interfaces:**
- Consumes: public web URL, BFF health URL, API health URL, optional worker signal, and optional Playwright base URL.
- Produces: `PreReleaseSmokeResult` with per-check status, bounded diagnostics, and no response-body secrets.

- [ ] **Step 1: Write offline tests for success and failure**

```python
def test_smoke_result_requires_web_bff_and_api_success(http_server):
    result = verify_prerelease_smoke(
        web_url=http_server.web,
        bff_health_url=http_server.bff_health,
        api_health_url=http_server.api_health,
    )
    assert result.ok
    assert {check.name for check in result.checks} >= {"web", "bff", "api"}

def test_smoke_failure_does_not_include_response_body(http_server):
    result = verify_prerelease_smoke(
        web_url=http_server.web,
        bff_health_url=http_server.bff_failure,
        api_health_url=http_server.api_health,
    )
    assert not result.ok
    assert "password" not in result.summary.lower()
```

- [ ] **Step 2: Run focused tests to verify the missing implementation**

Run: `python -m pytest tests/test_prerelease_smoke.py -q`

Expected: FAIL because the remote smoke verifier does not exist.

- [ ] **Step 3: Implement bounded HTTP checks**

Reuse the readiness checker’s status semantics: require HTTP 2xx, require `status=ok` for JSON health payloads, cap response details, and enforce a finite timeout. Make URLs explicit CLI arguments; do not infer production or local targets from ambient environment variables.

- [ ] **Step 4: Add worker and migration evidence inputs**

Accept sanitized Darkube worker-status/log evidence and a migration-head value from the operator workflow. Mark worker/migration checks failed when the evidence is absent; never claim that API health proves worker health or schema readiness.

- [ ] **Step 5: Wire the workflow-dispatch verification**

Run the smoke verifier, the existing Playwright login-to-Atlas test against the supplied pre-release base URL, and `slo_probe.py`. Upload only JUnit/text summaries and sanitized evidence.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_prerelease_smoke.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/verify_prerelease_smoke.py scripts/verify_deploy_readiness.py scripts/verify_e2e_environment.py tests/test_prerelease_smoke.py .github/workflows/darkube-prerelease.yml
git commit -m "test: verify remote Darkube prerelease health"
```

## Task 5: Add sanitized release and rollback evidence

**Files:**
- Create: `scripts/write_prerelease_evidence.py`
- Create: `tests/test_prerelease_evidence.py`
- Create: `docs/saas/prerelease-evidence.md`
- Modify: `docs/saas/phase-1-entry-evidence.md`

**Interfaces:**
- Consumes: Task 3 release identity, Task 4 results, Darkube build IDs, opaque database resource ID, migration head, operator, and rollback result.
- Produces: `PreReleaseEvidence` JSON with secret rejection and stable fields for the runbook and architecture status.

- [ ] **Step 1: Write evidence tests**

```python
def test_evidence_rejects_database_url_and_secret_values():
    evidence = valid_evidence()
    evidence.database_resource_id = "postgresql://user:password@host/db"
    with pytest.raises(ValueError, match="opaque"):
        write_prerelease_evidence(evidence, Path("evidence.md"))

def test_evidence_records_previous_version_rollback():
    evidence = valid_evidence(rollback="PASS")
    write_prerelease_evidence(evidence, Path("evidence.md"))
    assert '"rollback": "PASS"' in Path("evidence.md").read_text()
```

- [ ] **Step 2: Run tests to verify the missing implementation**

Run: `python -m pytest tests/test_prerelease_evidence.py -q`

Expected: FAIL because the evidence model/writer does not exist.

- [ ] **Step 3: Implement the evidence model and writer**

Validate commit SHA, namespace, four component IDs, opaque database ID, migration head, named operator, UTC timestamp, and enumerated result fields. Reject URLs, whitespace-bearing credentials, known placeholder markers, and secret-like key names. Write fenced JSON plus a short human-readable summary.

- [ ] **Step 4: Document the manual rollback rehearsal**

Record the exact Darkube UI action for selecting the previous successful build/commit, redeploying all four components, rerunning Task 4 checks, and retaining both failed and restored identities. If Darkube lacks a previous-build action, record the provider limitation and use the previous commit as the explicit manual redeployment source.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_prerelease_evidence.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/write_prerelease_evidence.py tests/test_prerelease_evidence.py docs/saas/prerelease-evidence.md docs/saas/phase-1-entry-evidence.md
git commit -m "ops: record sanitized prerelease evidence"
```

## Task 6: Complete the Darkube manual setup and disposable database rehearsal

**Files:**
- Modify: `deploy/darkube/prerelease/README.md`
- Modify: `docs/saas/prerelease-runbook.md`
- Create: `tests/test_prerelease_runbook_contract.py`

**Interfaces:**
- Consumes: Tasks 1-5 names, commands, env contract, evidence schema, and provider confirmation gates.
- Produces: a repeatable console procedure for creating, resetting, inspecting, and deleting the namespace and its synthetic database.

- [ ] **Step 1: Write runbook contract tests**

```python
def test_runbook_contains_all_four_apps_and_private_database_rules():
    text = Path("docs/saas/prerelease-runbook.md").read_text().lower()
    for name in ("web", "bff", "api", "worker", "postgresql"):
        assert name in text
    assert "public access" in text
    assert "synthetic" in text

def test_runbook_prohibits_production_data():
    text = Path("deploy/darkube/prerelease/README.md").read_text().lower()
    assert "production data" in text
    assert "must not" in text
```

- [ ] **Step 2: Run the contract test**

Run: `python -m pytest tests/test_prerelease_runbook_contract.py -q`

Expected: FAIL until the runbook contains the complete procedure and contract wording.

- [ ] **Step 3: Document manual setup in order**

Document: create namespace/project; create private managed PostgreSQL; create the four GitHub-connected apps; set Dockerfile/context/command/port; configure internal URLs; configure web/BFF ingress and TLS; set non-production secrets; deploy the `pre-release` commit; run the one-time migration; run health/smoke checks; collect logs; and record evidence.

- [ ] **Step 4: Document reset and destroy**

The reset procedure deletes and recreates only `okr-pre-release` resources, generates new synthetic secrets, recreates the disposable database, reruns migrations, and reruns smoke tests. It must explicitly state that no real customer data or production resource may be used.

- [ ] **Step 5: Perform the provider confirmation checklist**

Use the Darkube console to confirm repository connection, branch selection, monorepo Dockerfile paths, internal service routing, managed PostgreSQL version/address, secret handling, TLS, logs, previous-build redeploy, and namespace deletion. Record each result as `PASS`, `FAIL`, or `NOT AVAILABLE` with a provider screenshot/link or operator note; do not replace `NOT AVAILABLE` with an assumption.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_prerelease_runbook_contract.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add deploy/darkube/prerelease/README.md docs/saas/prerelease-runbook.md tests/test_prerelease_runbook_contract.py
git commit -m "docs: document disposable Darkube setup and reset"
```

## Task 7: Execute the first end-to-end pre-release deployment

**Files:**
- Modify: `docs/saas/prerelease-evidence.md`
- Modify: `docs/saas/prerelease-runbook.md`
- Modify: `docs/architecture-status.md`
- Modify: `docs/launcher-command-matrix.md`

**Interfaces:**
- Consumes: the merged protected `pre-release` commit, Darkube console, disposable database, Tasks 4-6 verification/evidence commands.
- Produces: a real pre-release deployment record and a tested redeployment of the previous known-good version.

- [ ] **Step 1: Create a synthetic-only pre-release change**

Use a harmless documented change or the approved branch tip. Confirm the commit contains no production secrets, customer records, or provider credentials before opening the pull request.

- [ ] **Step 2: Merge only after GitHub checks pass**

Confirm the protected branch requires the workflow status and review. Capture the Git commit SHA and GitHub workflow run ID.

- [ ] **Step 3: Deploy through Darkube GitHub integration**

Confirm all four apps build from the same commit, database connectivity is private, and the runtime profile is accepted. Capture Darkube build/deployment IDs and links to build/runtime logs.

- [ ] **Step 4: Run migration and verification**

Run the controlled Alembic head migration once, then run `verify_prerelease_smoke.py`, the existing Playwright login-to-Atlas test with the pre-release base URL, and `slo_probe.py`. Capture worker status/log evidence separately.

- [ ] **Step 5: Rehearse previous-version redeployment**

Deploy the previous known-good Darkube build or commit, rerun health/smoke checks, then restore the newer version if required. Record both transitions and the operator identity. This is an application redeployment rehearsal, not a database rollback rehearsal.

- [ ] **Step 6: Write evidence**

Run the evidence writer with actual sanitized IDs/results. Verify that the output contains no URL credentials, tokens, passwords, or raw environment dumps.

- [ ] **Step 7: Update status documentation**

Record the result in `docs/architecture-status.md`, link the evidence from `docs/saas/phase-1-entry-evidence.md`, and add the pre-release journey to `docs/launcher-command-matrix.md`. Keep production provider/backup/operations gates explicitly open.

- [ ] **Step 8: Commit**

```bash
git add docs/saas/prerelease-evidence.md docs/saas/prerelease-runbook.md docs/architecture-status.md docs/launcher-command-matrix.md
git commit -m "docs: record first Darkube prerelease rehearsal"
```

## Task 8: Final hardening and handoff

**Files:**
- Modify: `.github/workflows/darkube-prerelease.yml`
- Modify: `docs/saas/prerelease-runbook.md`
- Modify: `docs/saas/prerelease-evidence.md`
- Modify: `docs/architecture-status.md`
- Test: all files created by Tasks 1-7

**Interfaces:**
- Consumes: the first real deployment evidence and any provider `NOT AVAILABLE` findings.
- Produces: a repeatable handoff with explicit operational limits and no accidental production promotion path.

- [ ] **Step 1: Run the full focused suite**

Run: `python -m pytest tests/test_prerelease_config.py tests/test_prerelease_workflow_contract.py tests/test_prerelease_build.py tests/test_prerelease_smoke.py tests/test_prerelease_evidence.py tests/test_prerelease_runbook_contract.py -q`

Expected: PASS for all pre-release-specific tests.

- [ ] **Step 2: Run existing repository gates relevant to the change**

Run: `python scripts/check_deploy_config.py --mode template --env-file deploy/darkube/prerelease/.env.example`, `python scripts/check_import_boundaries.py`, `python scripts/check_docs_hq_links.py`, and the existing backend/SPA test commands used by `ci.yml`.

Expected: PASS without weakening an existing gate.

- [ ] **Step 3: Inspect the workflow and evidence for release safety**

Confirm the workflow has no SSH deployment, no production environment, no unrestricted provider token, no mutable `latest` release identity, and no upload of dotenv contents. Confirm evidence includes actual deployment and rollback IDs but no secrets.

- [ ] **Step 4: Record unresolved provider limits**

For every Hamravesh capability not available in the console, record `NOT AVAILABLE`, impact, and the manual workaround or next confirmation request. Do not claim API-driven deployment, provider-backed backup, or production rollback.

- [ ] **Step 5: Mark the handoff state**

Set the documentation state to `PRE-RELEASE VERIFIED` only if the end-to-end deployment and redeployment rehearsal passed. If any provider gate failed, set it to `PRE-RELEASE BLOCKED` with the exact failing gate. In either case, keep production SaaS readiness blocked.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/darkube-prerelease.yml docs/saas/prerelease-runbook.md docs/saas/prerelease-evidence.md docs/architecture-status.md
git commit -m "docs: hand off Darkube prerelease infrastructure"
```

## Completion definition

The implementation plan is complete only when the protected GitHub `pre-release` branch deploys all four apps in Darkube, the private synthetic PostgreSQL schema reaches Alembic head, health/smoke/worker/log checks pass, a previous version is redeployed successfully, evidence is sanitized and recorded, and the disposable namespace can be reset or deleted independently. This completion does not authorize production data, company-server deployment, tenant/RLS work, or production SaaS promotion.
