# OKR Tracker

A backend-first OKR platform with a Streamlit UI layer, secure backend mutations, and async worker support. The embedded backend path in `streamlit_app/app.py` is a Streamlit Cloud compatibility mode.

This README stays concise on implementation mechanics while making core policy concerns explicit. Detailed behavior, operations, and role playbooks live in the documents below.

## Read First: Fundamental Concern

This product exists to solve a management failure that is easy to miss:
- Teams can look busy while strategic performance does not improve.
- Routine operational work (BAU) can be mistaken for OKR progress.
- Leadership then makes decisions on activity volume instead of outcome change.

Core operating model:
- BAU (Business as Usual): keeps current operations stable and reliable.
- OKR (Objectives and Key Results): changes system performance and moves KPI baselines.

Non-negotiable boundary:
- BAU completion is not KR progress evidence.
- KR progress evidence must show measurable KPI baseline movement.
- BAU must be managed in external operational systems/governance artifacts (for example Odoo/ticketing/paper), not in KR check-in fields.

What every reviewer should verify:
1. Strategic lane and operational lane are separated in weekly governance outputs.
2. Throughput/activity-only KRs are rewritten into true change KRs.
3. BAU candidates are released or converted, not silently kept under strategic KRs.
4. Risk and coaching decisions use outcome deltas, not task volume.

Boundary policy references:
- EN: [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md)
- FA: [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md)

## Documentation HQ

Use this section as the primary index for all project docs.

### Core Product Guides

- Architecture (system): [ARCHITECTURE.md](ARCHITECTURE.md)
- Maintainer map: [CODEBASE_MAP.md](CODEBASE_MAP.md)
- User Guide (EN): [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- User Guide (FA): [docs/USER_GUIDE_FA.md](docs/USER_GUIDE_FA.md)
- Manager Playbook (EN): [docs/MANAGER_PLAYBOOK.md](docs/MANAGER_PLAYBOOK.md)
- Manager Playbook (FA): [docs/MANAGER_PLAYBOOK_FA.md](docs/MANAGER_PLAYBOOK_FA.md)
- Admin Guide (EN): [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md)
- Admin Guide (FA): [docs/ADMIN_GUIDE_FA.md](docs/ADMIN_GUIDE_FA.md)
- AI Features (EN): [docs/AI_FEATURES_GUIDE.md](docs/AI_FEATURES_GUIDE.md)
- AI Features (FA): [docs/AI_FEATURES_GUIDE_FA.md](docs/AI_FEATURES_GUIDE_FA.md)
- OKR Lifecycle (EN): [docs/OKR_LIFECYCLE_GUIDE.md](docs/OKR_LIFECYCLE_GUIDE.md)
- OKR Lifecycle (FA): [docs/OKR_LIFECYCLE_GUIDE_FA.md](docs/OKR_LIFECYCLE_GUIDE_FA.md)
- OKR vs BAU Boundary (EN): [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md)
- OKR vs BAU Boundary (FA): [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md)
- OKR Rollout (EN): [docs/OKR_ROLLOUT_GUIDE.md](docs/OKR_ROLLOUT_GUIDE.md)
- OKR Rollout (FA): [docs/OKR_ROLLOUT_GUIDE_FA.md](docs/OKR_ROLLOUT_GUIDE_FA.md)
- Learning Loop workflow (EN+FA): [docs/learning-loop.md](docs/learning-loop.md)
- Learning Loop architecture contract (EN+FA): [docs/LEARNING_LOOP_ARCHITECTURE.md](docs/LEARNING_LOOP_ARCHITECTURE.md)

### Rollout Templates

- Charter (EN): [docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE.md](docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE.md)
- Readiness checklist (EN): [docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md](docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md)
- Pilot retro survey (EN): [docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE.md](docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE.md)
- BAU release log (EN): [docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md](docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md)
- Charter (FA): [docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE_FA.md](docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE_FA.md)
- Readiness checklist (FA): [docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST_FA.md](docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST_FA.md)
- Pilot retro survey (FA): [docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE_FA.md](docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE_FA.md)

### Ops and Deployment

- Enterprise deployment (EN, detailed): [DEPLOYMENT.md](DEPLOYMENT.md)
- Enterprise deployment (FA, concise): [DEPLOYMENT_FA.md](DEPLOYMENT_FA.md)
- Troubleshooting (EN): [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Troubleshooting (FA): [docs/TROUBLESHOOTING_FA.md](docs/TROUBLESHOOTING_FA.md)
- Resilience verification runbook (EN): [docs/RESILIENCE_VERIFICATION.md](docs/RESILIENCE_VERIFICATION.md)
- Config reference (EN): [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)
- Config reference (FA): [docs/CONFIG_REFERENCE_FA.md](docs/CONFIG_REFERENCE_FA.md)
- Deployment compatibility redirects:
  - [docs/DEPLOYMENT_OPERATIONS_GUIDE.md](docs/DEPLOYMENT_OPERATIONS_GUIDE.md)
  - [docs/DEPLOYMENT_OPERATIONS_GUIDE_FA.md](docs/DEPLOYMENT_OPERATIONS_GUIDE_FA.md)
  - [docs/DOCKER_COMPOSE.md](docs/DOCKER_COMPOSE.md)
  - [docs/DOCKER_COMPOSE_FA.md](docs/DOCKER_COMPOSE_FA.md)
  - [docs/KUBERNETES.md](docs/KUBERNETES.md)
  - [docs/KUBERNETES_FA.md](docs/KUBERNETES_FA.md)
  - [docs/REVERSE_PROXY.md](docs/REVERSE_PROXY.md)
  - [docs/REVERSE_PROXY_FA.md](docs/REVERSE_PROXY_FA.md)

### Planning, Performance, and History

- V2 prioritized backlog: [docs/V2_PRIORITIZED_ISSUE_LIST.md](docs/V2_PRIORITIZED_ISSUE_LIST.md)
- Performance baselines: [performance.md](performance.md)
- Documentation archive index: [docs/archive/README.md](docs/archive/README.md)

## Start Here

### Persian-First Paths

- Member: [docs/USER_GUIDE_FA.md](docs/USER_GUIDE_FA.md)
- Manager: [docs/MANAGER_PLAYBOOK_FA.md](docs/MANAGER_PLAYBOOK_FA.md)
- Admin/Operator: [docs/ADMIN_GUIDE_FA.md](docs/ADMIN_GUIDE_FA.md)
- OKR transformation lead: [docs/OKR_ROLLOUT_GUIDE_FA.md](docs/OKR_ROLLOUT_GUIDE_FA.md)
- OKR/BAU boundary owner: [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md)

### By Goal

| Goal | Read First | Then Read |
| --- | --- | --- |
| Run locally and explore product behavior | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | [docs/MANAGER_PLAYBOOK.md](docs/MANAGER_PLAYBOOK.md) |
| First production deployment | [DEPLOYMENT.md](DEPLOYMENT.md) | [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md) |
| Configure runtime safely | [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md) | [docs/DOCKER_COMPOSE.md](docs/DOCKER_COMPOSE.md) |
| Operate incident/day-2 | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Roll out OKRs across departments | [docs/OKR_ROLLOUT_GUIDE.md](docs/OKR_ROLLOUT_GUIDE.md) | [docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md](docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md) |
| Prevent BAU contamination in OKRs | [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md) | [docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md](docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md) |

### By Role

| Role | Primary Guide (EN) | Primary Guide (FA) |
| --- | --- | --- |
| Member | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | [docs/USER_GUIDE_FA.md](docs/USER_GUIDE_FA.md) |
| Manager | [docs/MANAGER_PLAYBOOK.md](docs/MANAGER_PLAYBOOK.md) | [docs/MANAGER_PLAYBOOK_FA.md](docs/MANAGER_PLAYBOOK_FA.md) |
| Admin/Operator | [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | [docs/ADMIN_GUIDE_FA.md](docs/ADMIN_GUIDE_FA.md) |
| OKR transformation lead | [docs/OKR_ROLLOUT_GUIDE.md](docs/OKR_ROLLOUT_GUIDE.md) | [docs/OKR_ROLLOUT_GUIDE_FA.md](docs/OKR_ROLLOUT_GUIDE_FA.md) |
| OKR/BAU boundary owner | [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md) | [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md) |
| AI/policy reviewer | [docs/AI_FEATURES_GUIDE.md](docs/AI_FEATURES_GUIDE.md) | [docs/AI_FEATURES_GUIDE_FA.md](docs/AI_FEATURES_GUIDE_FA.md) |

## Deployment Intent

- Primary production design: `okr` + `backend-api` + `backend-worker` (self-hosted backend server architecture).
- Embedded backend in `app.py` is for Streamlit Cloud compatibility and MVP/demo hosting.
- Runtime behavior is backend-segregated: frontend reads/writes and heavy jobs are backend-owned (fail-closed on backend transport failure).
- Corporate deployments (AWS/ECS/Kubernetes/VM) should follow [DEPLOYMENT.md](DEPLOYMENT.md), not embedded mode.

## Quickstart (Local Development)

Prerequisites:

- Python 3.11+
- Supabase/PostgreSQL connection string (or local test DB)

Run:

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --require-hashes -r streamlit_app/requirements-dev.txt
$env:OKR_BACKEND_API_URL="auto"
streamlit run streamlit_app/app.py
```

macOS/Linux bash:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r streamlit_app/requirements-dev.txt
export OKR_BACKEND_API_URL=auto
streamlit run streamlit_app/app.py
```

Optional provider health check:

```bash
python streamlit_app/scripts/ai_provider_health_check.py
```

## Quickstart (Self-Hosted Docker Compose)

```bash
cp deploy/docker/.env.example deploy/docker/.env
python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml
docker compose -f deploy/docker/docker-compose.yml up -d --build
```

Then follow full production hardening in:

- [DEPLOYMENT.md](DEPLOYMENT.md)
- [docs/DEPLOYMENT_OPERATIONS_GUIDE.md](docs/DEPLOYMENT_OPERATIONS_GUIDE.md)

## Security Defaults (Production)

- Keep `OKR_BACKEND_PROXY_MUTATIONS=true`.
- Keep backend API private (internal only).
- Set strong values for:
  - `OKR_BACKEND_SERVICE_TOKEN`
  - `OKR_BACKEND_SIGNING_SECRET`
  - `OKR_BOOTSTRAP_ADMIN_PASSWORD`
- Use least-privilege DB role (not `postgres`).
- Keep fail-open toggles disabled in production.
- Keep `ALLOW_EXTERNAL_AI=false` unless policy-approved.

See authoritative config policy in [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md).

## Developer Fast Loop

```bash
pre-commit run --all-files
python scripts/check_docs_hq_links.py
python -m pytest -q
```

Benchmark hot paths when changing performance-sensitive code:

```bash
python streamlit_app/scripts/perf_hotpaths.py
```

Run Playwright happy-path e2e test (login -> focus map -> start timer):

Windows PowerShell:

```powershell
$env:OKR_RUN_PLAYWRIGHT_E2E="1"
python -m pytest -q tests/test_e2e_playwright_login_to_atlas.py
```

macOS/Linux bash:

```bash
export OKR_RUN_PLAYWRIGHT_E2E=1
python -m pytest -q tests/test_e2e_playwright_login_to_atlas.py
```

Install browser runtime once if needed:

```bash
playwright install chromium
```
