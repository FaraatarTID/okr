# GitHub -> Darkube Disposable Pre-Release Infrastructure Design

Documentation HQ: [README](../../../README.md)

**Status:** APPROVED IMPLEMENTATION SPECIFICATION

**Date:** 2026-09-01

**Decision:** Establish a disposable pre-release environment on Hamravesh Darkube. GitHub Actions remains the quality gate and publishes immutable commit-SHA images to private GHCR; Darkube pulls those images. No company-server access, production data, production credentials, provider API, or production SaaS promotion is required for this phase.

## 1. Purpose and scope

This design creates the first remotely runnable release path before the company CI/CD server is available. It proves that the current application can be built, configured, deployed, observed, smoke-tested, and redeployed on a real cloud platform using only GitHub and Darkube.

The environment is intentionally disposable. It is suitable for synthetic demonstrations, integration testing, and deployment rehearsal. It is not a production environment, customer environment, disaster-recovery target, or evidence of production SaaS readiness.

### In scope

- A protected GitHub `pre-release` deployment branch.
- GitHub Actions validation, tests, security checks, and Docker build checks.
- One Darkube namespace/project dedicated to pre-release.
- Separate Darkube applications for `spa-web`, `spa-bff`, `backend-api`, and `backend-worker`.
- One disposable synthetic PostgreSQL database, preferably Hamravesh managed PostgreSQL with public access disabled.
- Runtime configuration and generated non-production secrets held in Darkube configuration, not Git.
- Health, smoke, logs, deployment identity, and rollback/redeployment evidence.
- A documented manual Darkube setup and manual fallback where public provider automation details are unavailable.

### Out of scope

- Access to the company server, company GitLab, or company staging.
- Production deployment, production domains, production credentials, or real customer data.
- Customer provisioning, the SaaS control plane, tenant identifiers, shared-database RLS, or tenant schema work.
- Provider API/Terraform automation before Hamravesh confirms an authenticated interface.
- Long-term backups, production RPO/RTO, production HA, compliance certification, or customer onboarding.
- Replacing the existing on-premise Docker Compose deployment.

## 2. Repository baseline

The design follows the current repository rather than inventing a second runtime:

- [.github/workflows/ci.yml](../../.github/workflows/ci.yml) already runs migration/RLS checks, backend quality, SPA quality, Compose smoke, PostgreSQL integration, and Playwright E2E.
- [.github/workflows/docker-deploy.yml](../../.github/workflows/docker-deploy.yml) currently builds only one mutable backend `latest` image and contains an optional SSH deployment path. It is not the pre-release deployment path.
- [.github/workflows/release-runtime-gate.yml](../../.github/workflows/release-runtime-gate.yml) validates a supplied runtime dotenv blob but does not deploy a target.
- [deploy/docker/docker-compose.yml](../../deploy/docker/docker-compose.yml) models `postgres`, `backend-api`, `backend-worker`, `spa-bff`, and `spa-web`, and already exposes release image variables and SaaS profile variables. Its Compose behavior is authoritative for local operation, not automatically for Darkube.
- [deploy/docker/Dockerfile](../../deploy/docker/Dockerfile), [spa-bff/Dockerfile](../../spa-bff/Dockerfile), and [spa-web/Dockerfile](../../spa-web/Dockerfile) provide the three image build definitions. The API and worker intentionally share the backend image and use different commands.
- [scripts/check_deploy_config.py](../../scripts/check_deploy_config.py) provides fail-closed runtime configuration validation.
- [scripts/verify_deploy_readiness.py](../../scripts/verify_deploy_readiness.py) verifies backend, BFF, web, and Compose readiness for reachable targets.
- [scripts/verify_e2e_environment.py](../../scripts/verify_e2e_environment.py), [scripts/slo_probe.py](../../scripts/slo_probe.py), and [tests/test_e2e_playwright_spa_login_to_atlas.py](../../tests/test_e2e_playwright_spa_login_to_atlas.py) provide reusable verification surfaces.
- [src/saas/environment_contract.py](../../src/saas/environment_contract.py) and [src/saas/environment_config.py](../../src/saas/environment_config.py) define the dedicated single-tenant profile contract. This pre-release environment may use the contract for profile safety, but it must not be represented as a customer environment.
- [src/saas/provisioning.py](../../src/saas/provisioning.py), [src/saas/release_operations.py](../../src/saas/release_operations.py), [src/saas/backup_operations.py](../../src/saas/backup_operations.py), and [src/saas/control_plane.py](../../src/saas/control_plane.py) remain provider-neutral/local contracts. They are not a substitute for Darkube deployment automation in this phase.

## 3. Target topology

```text
Pull request -> protected pre-release branch
                     |
                     v
              GitHub Actions
       validate -> test -> security -> build checks
                     |
             required branch status
                     |
                     v
          GitHub Actions -> private GHCR -> Darkube image deployment
             namespace: okr-pre-release
                     |
      +--------------+---------------+----------------+
      |              |               |                |
   spa-web        spa-bff       backend-api      backend-worker
   public         edge app      internal app     internal worker
                                      |
                                      v
                          disposable PostgreSQL
                         private, synthetic data only
```

### Component contract

| Component | Darkube application | Source/build | Runtime contract | Exposure |
|---|---|---|---|---|
| Web | `okr-prerelease-web` | GitHub `pre-release`, `spa-web/Dockerfile` | Next.js on port 3000 | Public HTTPS URL |
| BFF | `okr-prerelease-bff` | GitHub `pre-release`, `spa-bff/Dockerfile` | `node dist/src/server.js` on port 3001 | Public only if browser requests require it; otherwise internal |
| API | `okr-prerelease-api` | GitHub `pre-release`, `deploy/docker/Dockerfile` | `python -m backend_app.run_api` on port 8100 | Internal only; expose health through approved probe path |
| Worker | `okr-prerelease-worker` | GitHub `pre-release`, `deploy/docker/Dockerfile` | `python -m backend_app.worker` | No public ingress |
| Database | `okr-prerelease-postgres` | Hamravesh managed PostgreSQL preferred | PostgreSQL 16 baseline; PG17 is accepted only after migration/test confirmation | Private internal address only |

The API and worker must use the same commit and backend image build inputs. The web and BFF must use the same commit as the backend. A release is identified by Git commit SHA plus Darkube build/deployment identifiers; the system must not use `latest` as a release identity.

## 4. Data flow and deployment flow

1. A pull request targets the protected `pre-release` branch.
2. GitHub Actions runs repository quality gates, runtime-config checks, and build checks for all four application processes.
3. GitHub branch protection permits merge only after required checks pass and the pull request has the required review.
4. GitHub Actions builds and publishes the merged `pre-release` commit images to private GHCR.
5. Darkube pulls the matching commit-SHA images and deploys each configured application in the `okr-pre-release` namespace.
5. The operator records the commit SHA, Darkube build IDs, deployed application versions, public URLs, database resource identity, and build/runtime log links.
6. A post-deployment verification workflow receives the pre-release web/BFF/API URLs as non-production GitHub environment variables and runs health, smoke, and bounded SLO checks.
8. If verification fails, the operator stops using the environment and redeploys the previous known-good image tag through the Darkube UI. The rollback record includes reason, operator, prior/current identity, result, and verification output.

The initial integration deliberately does not make a provider API call from GitHub Actions. If Hamravesh later supplies a supported API or webhook contract, it can be added behind a provider adapter without changing the release evidence format or application contracts.

## 5. PostgreSQL and schema policy

The database is disposable and contains synthetic data only. It must be created separately from the four application apps, with public access disabled and private connectivity enabled. The preferred implementation is a small managed PostgreSQL instance in the same Hamravesh cluster/namespace where the application apps run, because the public documentation describes internal database addresses and managed PostgreSQL HA/PITR capabilities. The pre-release environment does not rely on those production features as evidence.

The database starts empty. A single controlled migration action applies the repository Alembic head before smoke testing. The migration action must run once per database reset and must not be started concurrently by API replicas. If Darkube cannot provide a one-shot job, the operator uses the documented Darkube terminal/console procedure and records the command output as evidence. No production database is touched.

The schema must remain the current application schema. This phase does not add tenant columns, RLS policies, shared-database tenancy, or SaaS customer records.

## 6. Runtime configuration

The pre-release profile uses:

```text
OKR_DEPLOYMENT_PROFILE=single_tenant_saas
OKR_SAAS_MODE=true
OKR_DATA_ACCESS_MODE=database
OKR_ENVIRONMENT_ID=okr-prerelease
OKR_CUSTOMER_ID=synthetic-prerelease
OKR_BACKUP_PROVIDER=deferred
OKR_BACKUP_SCHEDULE=deferred
OKR_BACKEND_ENFORCE_TOKEN=true
OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true
OKR_BACKEND_PROXY_MUTATIONS=true
OKR_BACKEND_PROXY_READS=true
OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false
OKR_ALLOW_LOCAL_READ_FALLBACK=false
OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false
OKR_ENFORCE_STRONG_PASSWORD_POLICY=true
OKR_STRICT_RUNTIME_PREFLIGHT=true
BFF_COOKIE_SECURE=true
```

The database URL points to the private Hamravesh database address. `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_ANON_KEY` remain empty because the SaaS profile explicitly disables the HTTPS Supabase fallback. `BFF_PUBLIC_ORIGIN` must use the actual pre-release BFF URL or the internal service name supported by Darkube’s networking model; this is a provider verification item, not an invented hostname.

The following values are generated only for this disposable environment and stored as Darkube secrets or protected GitHub environment values where verification requires them:

- Database password.
- Backend service token.
- Backend signing secret.
- BFF session secret of at least 32 characters.
- Synthetic bootstrap administrator password.
- Any optional AI/PDF provider key, disabled by default.

No production credential, customer credential, backup credential, or long-lived Hamravesh administrative token may be copied into the repository or GitHub logs.

## 7. Verification and evidence

### Required pre-deployment checks

- Python dependency installation and Ruff/import-boundary checks.
- Migration lint and migration graph validation.
- Backend test suite and PostgreSQL integration.
- SPA BFF allowlist check, tests, and build.
- SPA web typecheck, tests, coverage, and build.
- Docker build checks for backend, BFF, and web; API and worker command coverage must both be checked.
- Runtime configuration validation using `check_deploy_config.py --mode runtime --saas-only` against a generated non-production environment file.
- Secret-hygiene check proving no real secrets are present in the branch or generated evidence.

### Required post-deployment checks

- Public web URL returns HTTP 2xx and renders the application shell.
- BFF `/healthz` returns an `ok` JSON status when BFF is publicly reachable or through the provider-supported internal probe.
- Backend `/healthz` returns an `ok` JSON status through an internal or approved probe path.
- Worker is running according to Darkube application status and emits a startup/healthy log signal. If the application exposes a synthetic job path, one job is submitted and completion is recorded.
- Synthetic login and the existing login-to-Atlas Playwright journey pass against the pre-release URL.
- Database connectivity and Alembic head are confirmed.
- Build logs and runtime logs are accessible to the operator and contain no credentials.
- `slo_probe.py` is run against the public web/BFF/API probe surface with results attached as evidence.

### Evidence record

The evidence record is machine-readable JSON embedded in `docs/saas/prerelease-evidence.md` and contains:

```json
{
  "environment": "okr-prerelease",
  "source_ref": "pre-release",
  "commit_sha": "40-hex-character-git-sha",
  "darkube_namespace": "okr-pre-release",
  "darkube_build_ids": {
    "web": "provider-build-id",
    "bff": "provider-build-id",
    "api": "provider-build-id",
    "worker": "provider-build-id"
  },
  "database_resource_id": "opaque-provider-resource-id",
  "migration_head": "repository-revision",
  "health": "PASS",
  "smoke": "PASS",
  "rollback": "PASS",
  "operator": "named-operator",
  "observed_at": "UTC timestamp"
}
```

The example values are field-shape documentation only. Real evidence must contain the actual commit, provider IDs, test results, and operator identity. It must never contain connection URLs, passwords, tokens, or secret values.

## 8. Rollback and redeployment

The first rollback mechanism is Darkube-native redeployment of the previous successful build or previous Git commit. It does not rebuild from a moving branch and does not use mutable tags.

Rollback procedure:

1. Freeze further merges to `pre-release`.
2. Identify the failed deployment and previous known-good commit/build from the evidence record and Darkube history.
3. Use Darkube’s documented redeploy/version-selection action for all four application apps, keeping the component versions aligned.
4. Re-run database connectivity, health, smoke, and worker checks.
5. Record the rollback result and release identities.
6. If the schema changed, reset the disposable database and rerun the controlled migration path rather than attempting an unverified database downgrade.

The current repository’s provider-neutral release manager remains useful for recording release semantics, but it cannot claim a Darkube rollback until a real Darkube deployment has been rehearsed. A provider API-driven rollback is a later enhancement after Hamravesh confirms the API surface.

## 9. Security boundaries

- The `pre-release` branch is protected; direct pushes are disabled.
- GitHub Actions quality jobs use read-only repository permissions and do not receive production secrets.
- Darkube's private GHCR pull credential is configured in Darkube and is not exposed to ordinary workflow jobs. GitHub Actions uses the repository-scoped `GITHUB_TOKEN` only for GHCR publication.
- The database has no public access. API, worker, and database have no public ingress.
- Only synthetic identities and synthetic OKR records may be used.
- Every secret is environment-scoped, masked where GitHub stores it, excluded from artifacts, and rotated by destroying/recreating the disposable environment.
- The BFF remains the public application edge; direct browser access to the backend API is prohibited.
- Logs and evidence are sanitized before upload.
- No step may invoke `provision_saas_environment.py` against a real customer or claim that this environment closes the production Phase 1 gate.

## 10. Hamravesh assumptions and confirmation gates

The following are documented capabilities or explicit unknowns from the public Hamravesh material:

- Darkube can deploy Docker images or Git repositories and supports configurable resources and replicas.
- Darkube can translate a limited Docker Compose shape, but public documentation does not establish full Compose networking, build, restart, or dependency semantics.
- Managed PostgreSQL, private internal addresses, S3-compatible storage, load balancing, and application/runtime logs are documented.
- A public Hamravesh provisioning API, Terraform provider, deployment API, or complete GitHub Actions action was not identified.
- Public documentation does not establish service DNS names, cross-app private routing behavior, database version availability, build-log API access, log retention, or automated rollback API behavior.

Before implementation is declared ready, the operator must manually confirm in the Darkube console:

1. A GitHub repository can be connected to each app at the required monorepo path and Dockerfile.
2. The `pre-release` branch can be selected as the deployment source and a merged commit triggers the expected build.
3. The four apps can communicate using provider-supported internal addresses.
4. A managed PostgreSQL database can be attached privately to the apps and provides the required PostgreSQL version.
5. Environment variables/secrets can be configured without exposing them in logs.
6. Web/BFF ingress and TLS work with the chosen pre-release domain.
7. Darkube exposes sufficient build/runtime logs and a previous-build redeploy action.
8. The disposable namespace/project can be deleted without affecting any other environment.

If any item is unavailable, the implementation must stop at the affected gate and document the provider limitation rather than silently substituting public database access, shared production infrastructure, or an unverified API.

## 11. Acceptance criteria

The design is implemented successfully when:

- A pull request merged into protected `pre-release` cannot bypass required GitHub quality checks.
- All four application apps are built from the same commit and are deployed in the dedicated Darkube namespace.
- The synthetic PostgreSQL database is private, empty before migration, and reaches the repository Alembic head.
- The public web journey, BFF health, API health, worker status, and synthetic smoke test pass.
- Darkube build/runtime logs are available and sanitized.
- The previous known-good version can be redeployed without rebuilding or changing application source.
- Evidence records contain commit/build/database IDs, test results, operator, and timestamps without secrets.
- The environment can be destroyed and recreated without touching company or production systems.
- Production SaaS gates remain unchanged and blocked; no tenant/RLS or customer-data behavior is introduced.
