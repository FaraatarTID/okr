# Twelve-Factor SaaS Compliance Implementation Plan

Documentation HQ: [README](../../../README.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dedicated-server-per-customer OKR deployment demonstrably compliant with all twelve factors of the Twelve-Factor App methodology.

**Architecture:** Keep one repository producing immutable web, BFF, backend API, and worker artifacts. Treat each customer PostgreSQL database and provider runtime as attached resources, while keeping the application processes stateless apart from the database and explicitly managed operational state. Do not introduce shared multi-tenancy or RLS as part of this plan.

**Tech Stack:** Python 3.11+, FastAPI/Uvicorn, SQLAlchemy/Alembic, Node.js 22, Next.js, npm workspaces, Docker Compose, GitHub Actions, GHCR, and Darkube/Hamravesh for provider evidence.

**Spec:** [The Twelve-Factor App](https://12factor.net/)

## Global Constraints

- One GitHub codebase must support CI, staging, and production deployments.
- Production secrets must come from the provider secret store; never commit credentials.
- Production releases must use immutable commit-SHA or digest-pinned images.
- Customer deployments remain single-tenant and database-isolated; shared multi-tenancy/RLS is out of scope.
- Database backup and recovery remain production prerequisites and must be evidenced before customer data onboarding.
- Local CI helpers may generate disposable secrets only for temporary test resources.

---

## File Map

- Modify: `.github/workflows/ci.yml` to enforce the complete build/release/run contract.
- Modify: `.github/workflows/release-runtime-gate.yml` and `.github/workflows/promote-production.yml` to require immutable artifacts and promotion evidence.
- Modify: `deploy/docker/docker-compose.yml` and `deploy/docker/entrypoint.sh` to make process, port, shutdown, health, and attached-resource behavior explicit.
- Modify: `scripts/verify_postgresql_integration.py` and `scripts/verify_resilience.py` to make disposable local verification self-contained and non-conflicting.
- Create: `scripts/verify_twelve_factor_contract.py` for repository-level structural checks.
- Create: `tests/test_twelve_factor_contract.py` for regression coverage of the contract verifier.
- Modify: `docs/DEPLOYMENT_OPERATIONS_GUIDE.md` for operational procedures and evidence requirements.
- Modify: `README.md` for the canonical release and environment workflow.
- Create: `docs/saas/twelve-factor-evidence.md` for the factor-by-factor evidence ledger.
- Provider-only evidence: Darkube staging/production configuration and Hamravesh PostgreSQL backup/restore records; do not fabricate these in the repository.

## Implementation Tasks

### Task 1: Establish the factor evidence ledger

**Files:**
- Create: `docs/saas/twelve-factor-evidence.md`
- Modify: `README.md`

- [ ] Define one section for each factor with status, evidence command, artifact location, owner, and remaining provider dependency.
- [ ] Record the current repository evidence for codebase, dependencies, config, backing services, build/release/run, port binding, and admin processes.
- [ ] State explicitly that single-tenant-per-customer isolation replaces shared-tenant/RLS requirements for this product model.
- [ ] Add a rule that a factor is marked `PASS` only after its stated command or provider evidence succeeds.
- [ ] Add the ledger to the release checklist in `README.md`.

### Task 2: Enforce explicit dependencies and environment configuration

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`
- Modify: `deploy/docker/.env.example`, `deploy/docker/.env.saas.example`
- Modify: `scripts/check_deploy_config.py`
- Test: `tests/test_check_deploy_config_script.py`

- [ ] Make every runtime dependency explicit in the existing Python and npm manifests and ensure lockfiles are required in CI.
- [ ] Ensure production configuration rejects missing or placeholder secrets while development templates remain runnable with disposable values.
- [ ] Ensure configuration validation distinguishes environment variables from checked-in templates and never prints secret values.
- [ ] Add tests for missing secrets, placeholder secrets, and valid environment-driven configuration.
- [ ] Run `uv sync --locked --group dev`, `npm ci`, and both dependency-lock checks in CI.

### Task 3: Make build, release, and run artifacts immutable

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/publish-ghcr.yml`, `.github/workflows/release-runtime-gate.yml`, `.github/workflows/promote-production.yml`
- Modify: `deploy/docker/docker-compose.yml`
- Modify: `deploy/ghcr/README.md`

- [ ] Build web, BFF, and backend images once per commit and publish commit-SHA tags plus digests to private GHCR.
- [ ] Generate a release manifest containing image names, tags, digests, source commit, and workflow run ID.
- [ ] Require staging to deploy the exact manifest produced by CI; prohibit provider-side rebuilds.
- [ ] Require production promotion to reference the verified staging manifest and digest-pinned images.
- [ ] Add a CI test that fails if deployment configuration uses mutable `latest` tags.
- [ ] Verify the release gate, GHCR signature gate, and promotion workflow using a non-production release.

### Task 4: Complete stateless process, port binding, disposability, and concurrency contracts

**Files:**
- Modify: `deploy/docker/docker-compose.yml`, `deploy/docker/entrypoint.sh`
- Modify: `backend_app/run_api.py`, `backend_app/worker.py`
- Create: `scripts/verify_process_contract.py`
- Create: `tests/test_process_contract.py`

- [ ] Ensure API, worker, BFF, and web obtain ports and runtime settings from environment variables.
- [ ] Keep customer data in PostgreSQL and document every non-database volume as operational metadata with a recovery policy.
- [ ] Add graceful SIGTERM handling and bounded shutdown time for API, worker, and BFF processes.
- [ ] Verify health checks distinguish readiness from liveness and do not report healthy before required backing services are usable.
- [ ] Document independent horizontal scaling for API, BFF, and worker processes, including worker concurrency limits and duplicate-job protection.
- [ ] Add automated tests for environment-driven ports, shutdown handling, and process contract violations.

### Task 5: Standardize logs as event streams

**Files:**
- Modify: `backend_app/run_api.py`, `backend_app/worker.py`
- Modify: `spa-bff/src/server.ts` and the corresponding BFF logging module
- Create: `scripts/verify_logging_contract.py`
- Create: `tests/test_logging_contract.py`
- Modify: `docs/DEPLOYMENT_OPERATIONS_GUIDE.md`

- [ ] Emit one-line structured JSON events to stdout/stderr with timestamp, service, environment, release, request/correlation ID, level, and event name.
- [ ] Redact passwords, tokens, cookies, authorization headers, database URLs, and provider credentials before emission.
- [ ] Remove file-based runtime logging as a required operational path; retain local files only as optional developer diagnostics.
- [ ] Define provider retention, searchable fields, alert conditions, and correlation-ID troubleshooting steps.
- [ ] Add tests that verify required fields and secret redaction.

### Task 6: Establish development/staging/production parity

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `deploy/docker/docker-compose.yml`
- Modify: `docs/DEPLOYMENT_OPERATIONS_GUIDE.md`, `README.md`
- Create: `scripts/verify_environment_parity.py`
- Create: `tests/test_environment_parity.py`

- [ ] Define one versioned runtime matrix for Python, Node, PostgreSQL, image entrypoints, health endpoints, and migration policy.
- [ ] Make CI and local Compose use the same container entrypoints and release image contracts as staging.
- [ ] Add a staging-only configuration diff check that compares names/types/default policy without exposing secret values.
- [ ] Require the same commit-SHA image manifest in staging and production.
- [ ] Keep provider-specific differences limited to environment variables, networking, secret injection, and resource sizing.
- [ ] Record Darkube parity evidence when the provider is configured; until then keep the ledger `PENDING_PROVIDER_EVIDENCE`.

### Task 7: Verify attached backing services and admin processes

**Files:**
- Modify: `scripts/verify_postgresql_integration.py`, `scripts/verify_resilience.py`
- Create: `scripts/verify_admin_process_contract.py`
- Create: `tests/test_admin_process_contract.py`
- Modify: `docs/saas/hamravesh-backup-onboarding.md`, `docs/DEPLOYMENT_OPERATIONS_GUIDE.md`

- [ ] Keep PostgreSQL, cache, and external providers configurable by URL/name rather than hard-coded service identity.
- [ ] Make disposable verifier credentials process-local and ensure cleanup in every failure path.
- [ ] Make the PostgreSQL verifier select an available host port or fail with a clear remediation while preserving unrelated containers.
- [ ] Ensure migrations, health checks, seed operations, and recovery verification run as explicit one-off commands.
- [ ] Add a migration smoke sequence: upgrade from empty database, verify head, rerun idempotently, and report skipped tests distinctly from passed tests.
- [ ] Keep production backup/restore evidence separate from local disposable database verification.

### Task 8: Run provider evidence and close the ledger

**Files:**
- Modify: `docs/saas/twelve-factor-evidence.md`
- Modify: `docs/DEPLOYMENT_OPERATIONS_GUIDE.md`
- Evidence: Darkube project configuration, GHCR pull evidence, Hamravesh PostgreSQL evidence

- [ ] Deploy the immutable release manifest to Darkube staging with private API, worker, and database networking.
- [ ] Verify independent web/BFF/API/worker health, restart behavior, startup ordering, and failure isolation.
- [ ] Capture structured-log, latency, resource, and scaling evidence from staging.
- [ ] Perform the application rollback rehearsal using two immutable image manifests; verify the previous known-good pair is restored.
- [ ] Perform the approved production database backup and isolated restore rehearsal before customer-data onboarding.
- [ ] Mark each factor `PASS` only with attached sanitized evidence; otherwise retain `PENDING_PROVIDER_EVIDENCE`.

## Final Acceptance Gate

- [ ] `python scripts/verify_twelve_factor_contract.py` passes.
- [ ] `python -m pytest -q` passes with no unexpected skips.
- [ ] Exact CI mypy, Ruff, architecture, secret, OpenAPI, Docker-build, resilience, and PostgreSQL commands pass.
- [ ] CI publishes and verifies digest-pinned GHCR artifacts.
- [ ] Darkube staging evidence confirms parity, disposability, logs, scaling, and failure isolation.
- [ ] Application rollback evidence is sanitized and reproducible.
- [ ] Production database backup/restore evidence is validated separately.
- [ ] `docs/saas/twelve-factor-evidence.md` contains no unowned open item.
