Documentation HQ: [README](../README.md)

Hybrid Frontend Migration - Phase 0 Checklist

Date
- 2026-02-25

Purpose
- Run pre-migration checks before introducing SPA/BFF components.
- Capture a reproducible baseline and rollback readiness.

Exit Rule
- Phase 0 is complete only when every `Required` item below is checked and evidence is linked.

## 1. Environment And Config Gate

| Item | Required | Evidence |
| --- | --- | --- |
| `deploy/docker/.env` prepared for runtime mode | Yes | Path + commit/ops note |
| `deploy/secrets/secrets.toml` present (non-placeholder values where required) | Yes | Path + ops note |
| Runtime gate passes: `python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml` | Yes | Command output snapshot |
| `OKR_BACKEND_PROXY_MUTATIONS=true` | Yes | `.env` line reference |
| `OKR_BACKEND_PROXY_READS=true` | Yes | `.env` line reference |
| `OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true` | Yes | `.env` line reference |
| `ALLOW_EXTERNAL_AI=false` (or explicit exception recorded) | Yes | `.env` line reference + approval note if exception |

## 2. Baseline Validation

| Item | Required | Evidence |
| --- | --- | --- |
| Unit/integration suite pass: `python -m pytest -q` | Yes | Test run summary |
| E2E pass: `OKR_RUN_PLAYWRIGHT_SPA_E2E=1` + `python -m pytest -q tests/test_e2e_playwright_spa_login_to_atlas.py` | Yes | Test run summary |
| Self-hosted services healthy (`okr`, `backend-api`, `backend-worker`) | Yes | `docker compose ... ps` output snapshot |
| Backend health endpoint responds: `curl -f http://127.0.0.1:8100/healthz` | Yes | Response snapshot |
| Login -> Atlas -> timer start/stop manual smoke is successful | Yes | Tester + timestamp |

## 3. Security Boundary Verification

| Item | Required | Evidence |
| --- | --- | --- |
| `backend-api` is not publicly routed by reverse proxy/ingress | Yes | Proxy config reference |
| Direct browser/network path to `backend-api` from public ingress is blocked | Yes | Test note (`expected blocked`) |
| Service token and signing secret are only in server-side runtime env | Yes | Secret inventory note |
| No frontend bundle contains `OKR_BACKEND_SERVICE_TOKEN` / `OKR_BACKEND_SIGNING_SECRET` values | Yes | Scan method + result |

## 4. Rollback Readiness

| Item | Required | Evidence |
| --- | --- | --- |
| Streamlit-first routing fallback is documented | Yes | Link to runbook section |
| One-command or one-toggle rollback path is defined | Yes | Command/toggle reference |
| Rollback owner and on-call contacts are assigned | Yes | Names/roles |
| Pilot-team communication template for rollback event exists | Yes | Message template reference |

## 5. Artifacts To Produce

- Baseline report file: `docs/HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.md`
- Runtime gate command output snapshot (attached in CI artifact or internal runbook).
- Rollback toggle contract note: `docs/HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.md`

## 6. Go/No-Go Decision

Decision
- [ ] `GO` - proceed to Phase 1 (contract inventory and API fit).
- [ ] `NO-GO` - block migration until failed items are remediated.

Approvals
- Engineering lead:
- Security/Platform reviewer:
- Date:

Blocking issues (if any)
- 
