# Twelve-Factor Hardening Implementation Plan

Documentation HQ: [README](../../../README.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every repository-verifiable Twelve-Factor criterion fail closed, while keeping provider-dependent evidence explicitly pending.

**Architecture:** `pyproject.toml` and `uv.lock` remain the dependency authority. Release descriptors require immutable digests and separate local development builds. Worker lifecycle safety is implemented with a heartbeat and bounded job lease recovery; provider evidence is represented by sanitized, schema-validated artifacts rather than fabricated claims.

**Tech Stack:** Python 3.11+, pytest, uv, Docker Compose, Kubernetes YAML, GitHub Actions.

**Spec:** `docs/saas/twelve-factor-evidence.md`

## Global Constraints

- Never read or modify `deploy/docker/.env`.
- Never claim Darkube, rollback, backup, restore, or live restart evidence without actual execution evidence.
- Keep local development defaults separate from release-required configuration.
- Preserve the existing API/BFF/worker process boundaries.

---

### Task 1: Dependency authority and release image contracts

**Files:**
- Create: `scripts/check_dependency_manifest.py`
- Create: `tests/test_dependency_manifest.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `deploy/docker/Dockerfile`
- Modify: `spa-bff/Dockerfile`
- Modify: `spa-web/Dockerfile`
- Modify: `deploy/docker/docker-compose.yml`
- Modify: `deploy/k8s/deployment-backend-api.yaml`
- Modify: `deploy/k8s/deployment-backend-worker.yaml`

- [x] Add a locked-manifest freshness check and digest validation tests.
- [x] Run the focused checks.

### Task 2: Worker disposability

**Files:**
- Modify: `backend_app/worker.py`
- Modify: `deploy/docker/docker-compose.yml`
- Modify: `tests/test_worker_observability.py`
- Modify: `tests/test_concurrency_disposability_contract.py`

- [x] Add heartbeat and bounded active-job recovery behavior.
- [x] Add healthcheck and behavior tests.

### Task 3: Provider parity and admin evidence

**Files:**
- Create: `scripts/verify_provider_evidence.py`
- Create: `tests/test_provider_evidence.py`
- Modify: `scripts/verify_environment_parity.py`
- Modify: `scripts/verify_admin_process_contract.py`
- Modify: `docs/saas/twelve-factor-evidence.md`

- [x] Validate sanitized evidence schemas and reject fabricated/incomplete evidence.
- [x] Keep missing provider evidence visibly pending.

### Task 4: Full verification

- [x] Run contract gates, secret hygiene, lint, typing, Compose rendering, and the full test suite.
- [x] Report passes, skips, and unresolved provider-dependent evidence separately.

## Completion note

Repository-side implementation is complete. The following remain intentionally
pending because they require configured external infrastructure and must not be
fabricated: Darkube live parity/restart evidence, provider rollback rehearsal,
and provider backup/restore execution.
