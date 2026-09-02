# OKR Tracker

An enterprise-ready OKR strategy and execution platform that keeps strategic change work separate from day-to-day operations.

This README is the fast starting point. It shows what this product is, what it is not, and where to start.

## Product scope

Atlas is an enterprise-oriented OKR platform foundation, not only a personal
tracking utility. The first SaaS operating model is single-tenant: each
enterprise receives an isolated application environment and dedicated
database. The repository can still be run locally or on-premise for individual
teams, but its architecture, security controls, and deployment contracts are
designed to support managed enterprise environments.

Suggested GitHub repository description: `Enterprise OKR strategy and
execution platform with isolated deployment support.`

`Atlas` means the main in-app workspace (Focus Task, Focus Map, and Inspector) after login.

## Glossary

- `Goal`: a clear narrative that defines the why, why it matters, and the intended change people can align around.
- `Objective`: the concrete strategic outcome under a goal for the cycle; it states what should be different and is validated by one or more KRs.
- `BAU` (Business as Usual): routine operational work that keeps current service running.
- `OKR`: strategic change work intended to improve system performance.
- `KR` (Key Result): one measurable proof line (`baseline -> target by time`) showing whether an objective is moving.
- `KPI baseline movement`: before/after metric change (not task completion count).
- `Atlas`: the in-app strategy workspace for OKR execution and evidence updates.

## Goal vs Objective vs KR Writing Standard

- `Goal` answers: "Why this change matters, where we are heading, and what strategic shift we intend."
- `Objective` answers: "What outcome state must exist by cycle end?"
- `KR` answers: "How will we verify that outcome numerically?"
- `Initiative/Task` answers: "How will we execute the change work?"

Objective quality bar:
- Outcome-oriented, not a task list.
- Time-bounded to the cycle.
- Usually needs 2-4 KRs to prove movement.
- Minimum activation rule is still 1 KR; `2-4` is the quality recommendation.

KR quality bar:
- One metric per KR.
- Must define `start/current/target` and unit.
- Progress is metric movement, not task completion.

Classification rule:
- Purpose, direction, and intended strategic shift -> `Goal`.
- Strategic outcome statement that may need multiple indicators -> `Objective`.
- Single measurable line ("from A to B by date") -> `KR`.
- Execution steps ("build, run, close, ship") -> `Initiative/Task` (not Objective/KR).

### Objective vs KR Quick Test (20 Seconds)

| If the statement is... | Classify as... | Reason |
| --- | --- | --- |
| Broad changed state ("faster, more reliable onboarding this quarter") | Objective | Needs multiple signals to prove it. |
| One numeric delta ("activation rate 42% -> 60% by Sep 30") | KR | It is already a metric proof line. |
| Action plan ("launch onboarding emails and rewrite docs") | Initiative/Task | It describes execution, not outcome proof. |

Example stack:
- Goal: "Make customer onboarding a strategic advantage."
- Objective: "Deliver a faster and more predictable onboarding experience this quarter."
- KR: "Increase activation rate from 42% to 60% by September 30."

## Atlas Design Philosophy

Atlas is designed as a strategy cockpit, not a daily task board.

- One workspace, one strategic narrative: Focus Task, Focus Map, and Inspector stay connected.
- Outcome evidence over activity volume: KR progress must tie to measurable KPI movement.
- Role-aware clarity: members, managers, and admins see the right scope without changing the model.
- Weekly governance ready: at-risk areas are visible for coaching and correction.
- BAU boundary by design: operational execution stays outside the app.

## Why This Exists Beside Conventional Management

Conventional management tools are still required, but they solve a different problem.

- Conventional tools (ERP, ticketing, project boards, to-do lists) manage operational execution.
- Atlas manages strategic change and outcome evidence.
- Mixing both in one lane creates false progress signals and weak leadership decisions.
- Separation keeps governance honest: BAU throughput in operational reports, KPI movement in KR reports.

## Quick Orientation (60 Seconds)

1. This app is for strategic OKR work only.
2. BAU execution stays in your existing operational tools.
3. A completed BAU task is never KR progress by itself.
4. KR progress must show measurable KPI movement.

## Non-Negotiable Rules

1. Do not store BAU tasks inside this app.
2. Do not use task count as KR progress evidence.
3. Do not report KR progress without a measurable metric delta.
4. Do track BAU in your existing operations system (ERP, ticketing, board, or notes).

## Choose Your Path (30 Seconds)

- I need policy clarity first: read `Read First: Fundamental Concern` and `OKR vs BAU Quick Test`.
- I am a member/manager/admin: go to `Start Here` then open one guide under `By Role`.
- I want to run the app locally: jump to `Quickstart (Local Development)`.
- I need production deployment: jump to `Quickstart (Self-Hosted Docker Compose)`, then [DEPLOYMENT.md](DEPLOYMENT.md).
- I am a non-technical reviewer: read `Read First`, `OKR vs BAU Quick Test`, and `First 5 Minutes in Atlas`, then stop.

Read in this order if you are new:
1. `Read First: Fundamental Concern`
2. `Atlas Design Philosophy`
3. `Product Scope in Plain Language`
4. `Start Here`
5. `Quickstart` (if you want to run the app)

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
- BAU must be tracked outside this app (for example in an operations board, ticket system, ERP workflow, or meeting notes).

What every reviewer should verify:
1. Strategic lane and operational lane are separated in weekly governance outputs.
2. Throughput/activity-only KRs are rewritten into true change KRs.
3. BAU candidates are released or converted, not silently kept under strategic KRs.
4. Risk and coaching decisions use outcome deltas, not task volume.

Boundary policy references:
- EN: [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md)
- FA: [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md)

## Product Scope

What this app is:
- An OKR workspace for strategy, key results, check-ins, and measurable outcome tracking.

What this app is not:
- A BAU task manager.
- A BAU deadline tracker.
- A replacement for ERP, ticketing, project board, or daily operations planning tools.

Hard rule:
- Do not enter BAU tasks as KR evidence in this app.
- If BAU work is important, track it in operational systems and discuss it in weekly operations check-ins.

## OKR vs BAU Quick Test (30 Seconds)

Use this rule before entering any update:
- If the work keeps current operations running, it is BAU and stays outside this app.
- If the work is intended to shift a KPI baseline, it is OKR work and belongs in this app.

Examples:
- BAU: "Close daily support tickets within SLA."
- OKR Objective: "Deliver faster customer support resolution this quarter."
- KR: "Reduce average ticket resolution time from 36h to 12h by end of quarter."

### Separation Decision Table

| Question | BAU (Operational) | OKR (Strategic) |
| --- | --- | --- |
| Primary purpose | Keep current service running | Change performance baseline |
| Where to track | ERP, ticketing, project board, meeting notes | Atlas (Objective/KR workflow) |
| Acceptable evidence | Completion, SLA adherence, throughput | Measurable before/after outcome delta |
| Should be entered as KR evidence in app? | No | Yes |
| If metric delta is missing | Keep outside app | Define metric first, then track |

### When You Are Unsure

1. Ask: "What exact metric will move?"
2. If you cannot name baseline and target, treat it as BAU.
3. Do not add BAU tags/placeholders in this app; keep BAU in operational systems.

### Common Classification Mistakes

| Statement | Correct classification | Correct handling |
| --- | --- | --- |
| "Close 100 support tickets this week." | BAU | Track in ticketing/operations tools, not KR evidence fields. |
| "Hold weekly sync meetings." | BAU | Keep in manager routines or project plan outside app. |
| "Update dashboard every day." | BAU | Track as operational hygiene, not strategic progress. |
| "Cut ticket resolution time from 36h to 12h." | OKR | Track as KR with explicit baseline, target, and evidence updates. |

## First 5 Minutes in Atlas

Use this flow to understand the product in one short pass:
1. Sign in and open Atlas.
2. Pick your cycle (manager/admin) or continue in the manager-assigned cycle (member).
3. Open one Objective/KR in Focus Map, then switch lens (`Focus`, `Health`, `Owner`) to review priorities.
4. Start one Focus Task timer, set an estimated time, then stop it with a short summary. Task progress auto-computes from time spent vs estimate.
5. Click "AI Analysis" below the Focus Map to auto-analyze all KRs and view results in their Inspector modals.

## Start Here

Pick exactly one path below first. Ignore the rest on first read.

If you want a zero-decision start:
1. Go to `By Role`.
2. Open one guide only.
3. Use `By Goal` and `Documentation HQ` later.
4. If you are a non-technical reviewer, you can stop after your role guide.

### English-First Paths

- Member: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- Manager: [docs/MANAGER_PLAYBOOK.md](docs/MANAGER_PLAYBOOK.md)
- Admin/Operator: [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md)
- OKR transformation lead: [docs/OKR_ROLLOUT_GUIDE.md](docs/OKR_ROLLOUT_GUIDE.md)
- OKR/BAU boundary owner: [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md)

### Persian-First Paths

- Member: [docs/USER_GUIDE_FA.md](docs/USER_GUIDE_FA.md)
- Manager: [docs/MANAGER_PLAYBOOK_FA.md](docs/MANAGER_PLAYBOOK_FA.md)
- Admin/Operator: [docs/ADMIN_GUIDE_FA.md](docs/ADMIN_GUIDE_FA.md)
- OKR transformation lead: [docs/OKR_ROLLOUT_GUIDE_FA.md](docs/OKR_ROLLOUT_GUIDE_FA.md)
- OKR/BAU boundary owner: [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md)

### By Goal

| Goal | Read First (EN / FA) | Then Read (EN / FA) |
| --- | --- | --- |
| Run locally and explore product behavior | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) / [docs/USER_GUIDE_FA.md](docs/USER_GUIDE_FA.md) | [docs/MANAGER_PLAYBOOK.md](docs/MANAGER_PLAYBOOK.md) / [docs/MANAGER_PLAYBOOK_FA.md](docs/MANAGER_PLAYBOOK_FA.md) |
| First production deployment | [DEPLOYMENT.md](DEPLOYMENT.md) / [DEPLOYMENT_FA.md](DEPLOYMENT_FA.md) | [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md) / [docs/CONFIG_REFERENCE_FA.md](docs/CONFIG_REFERENCE_FA.md) |
| Configure runtime safely | [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md) / [docs/CONFIG_REFERENCE_FA.md](docs/CONFIG_REFERENCE_FA.md) | [docs/DOCKER_COMPOSE.md](docs/DOCKER_COMPOSE.md) / [docs/DOCKER_COMPOSE_FA.md](docs/DOCKER_COMPOSE_FA.md) |
| Operate incident/day-2 | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) / [docs/TROUBLESHOOTING_FA.md](docs/TROUBLESHOOTING_FA.md) | [DEPLOYMENT.md](DEPLOYMENT.md) / [DEPLOYMENT_FA.md](DEPLOYMENT_FA.md) |
| Roll out OKRs across departments | [docs/OKR_ROLLOUT_GUIDE.md](docs/OKR_ROLLOUT_GUIDE.md) / [docs/OKR_ROLLOUT_GUIDE_FA.md](docs/OKR_ROLLOUT_GUIDE_FA.md) | [docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md](docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md) / [docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST_FA.md](docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST_FA.md) |
| Prevent BAU contamination in OKRs | [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md) / [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md) | [docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md](docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md) / [docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE_FA.md](docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE_FA.md) |

### By Role

| Role | Primary Guide (EN) | Primary Guide (FA) |
| --- | --- | --- |
| Member | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | [docs/USER_GUIDE_FA.md](docs/USER_GUIDE_FA.md) |
| Manager | [docs/MANAGER_PLAYBOOK.md](docs/MANAGER_PLAYBOOK.md) | [docs/MANAGER_PLAYBOOK_FA.md](docs/MANAGER_PLAYBOOK_FA.md) |
| Admin/Operator | [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | [docs/ADMIN_GUIDE_FA.md](docs/ADMIN_GUIDE_FA.md) |
| OKR transformation lead | [docs/OKR_ROLLOUT_GUIDE.md](docs/OKR_ROLLOUT_GUIDE.md) | [docs/OKR_ROLLOUT_GUIDE_FA.md](docs/OKR_ROLLOUT_GUIDE_FA.md) |
| OKR/BAU boundary owner | [docs/OKR_BAU_BOUNDARY_GUIDE.md](docs/OKR_BAU_BOUNDARY_GUIDE.md) | [docs/OKR_BAU_BOUNDARY_GUIDE_FA.md](docs/OKR_BAU_BOUNDARY_GUIDE_FA.md) |
| AI/policy reviewer | [docs/AI_FEATURES_GUIDE.md](docs/AI_FEATURES_GUIDE.md) | [docs/AI_FEATURES_GUIDE_FA.md](docs/AI_FEATURES_GUIDE_FA.md) |

## Documentation HQ

Use this section as the primary index for all project docs.
If you are a first-time reader, skip this section until after `Start Here`.

### Core Product Guides

- Architecture (system): [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
- Maintainer map: [CODEBASE_MAP.md](docs/architecture/CODEBASE_MAP.md)
- Architecture backlog: [ARCHITECTURE_BACKLOG.md](docs/architecture/ARCHITECTURE_BACKLOG.md)
- Archived architecture status ledger: [docs/archive/architecture-2026-08-31/architecture-status_2026-08-31.md](docs/archive/architecture-2026-08-31/architecture-status_2026-08-31.md)
- Architecture delivery system: [docs/ARCHITECTURE_DELIVERY_SYSTEM.md](docs/ARCHITECTURE_DELIVERY_SYSTEM.md)
- Documentation lifecycle registry: [docs/DOCUMENTATION_LIFECYCLE.md](docs/DOCUMENTATION_LIFECYCLE.md)
- Task-graph evaluation: [docs/TASK_GRAPH_EVALUATION.md](docs/TASK_GRAPH_EVALUATION.md)
- Enterprise SaaS roadmap: [ENTERPRISE_SAAS_ROADMAP.md](docs/architecture/ENTERPRISE_SAAS_ROADMAP.md)
- Pre-SaaS architecture simplification: [PRE_SAAS_ARCHITECTURE_BACKLOG.md](docs/architecture/PRE_SAAS_ARCHITECTURE_BACKLOG.md)
- Multi-tenant data access ADR: [docs/ADR-001-multitenant-data-access-boundary.md](docs/ADR-001-multitenant-data-access-boundary.md)
- Archived reliability roadmap: [ENTERPRISE_RELIABILITY_ROADMAP_REWRITABLE.md](docs/architecture/ENTERPRISE_RELIABILITY_ROADMAP_REWRITABLE.md)
- Production readiness runbooks and dashboards: [docs/OBSERVABILITY_AND_RUNBOOKS.md](docs/OBSERVABILITY_AND_RUNBOOKS.md)
- Operations readiness and recovery: [docs/OPS_READINESS_AND_RECOVERY_GUIDE.md](docs/OPS_READINESS_AND_RECOVERY_GUIDE.md)
- Quality gate baseline: [docs/QUALITY_GATE_BASELINE.md](docs/QUALITY_GATE_BASELINE.md)
- Manager active-cycle plan: [docs/PLAN_PER_MANAGER_ACTIVE_CYCLES.md](docs/PLAN_PER_MANAGER_ACTIVE_CYCLES.md)
- SPA BFF service guide: [spa-bff/README.md](spa-bff/README.md)
- Backend API and worker guide: [backend_app/README.md](backend_app/README.md)
- SPA web service guide: [spa-web/README.md](spa-web/README.md)
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

### Rollout Templates

All templates in this section are external governance documents, not app data-entry screens.

- Charter (EN): [docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE.md](docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE.md)
- Readiness checklist (EN): [docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md](docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md)
- Pilot retro survey (EN): [docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE.md](docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE.md)
- BAU release log (EN): [docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md](docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md)
- Charter (FA): [docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE_FA.md](docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE_FA.md)
- Readiness checklist (FA): [docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST_FA.md](docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST_FA.md)
- Pilot retro survey (FA): [docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE_FA.md](docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE_FA.md)
- BAU release log (FA): [docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE_FA.md](docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE_FA.md)

### Ops and Deployment

- Enterprise deployment (EN, detailed): [DEPLOYMENT.md](DEPLOYMENT.md)
- Enterprise deployment (FA, concise): [DEPLOYMENT_FA.md](DEPLOYMENT_FA.md)
- Troubleshooting (EN): [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Troubleshooting (FA): [docs/TROUBLESHOOTING_FA.md](docs/TROUBLESHOOTING_FA.md)
- Config reference (EN): [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)
- Config reference (FA): [docs/CONFIG_REFERENCE_FA.md](docs/CONFIG_REFERENCE_FA.md)
- Compatibility redirect: [docs/DEPLOYMENT_OPERATIONS_GUIDE.md](docs/DEPLOYMENT_OPERATIONS_GUIDE.md)
- Compatibility redirect: [docs/DEPLOYMENT_OPERATIONS_GUIDE_FA.md](docs/DEPLOYMENT_OPERATIONS_GUIDE_FA.md)
- Compatibility redirect: [docs/DOCKER_COMPOSE.md](docs/DOCKER_COMPOSE.md)
- Compatibility redirect: [docs/DOCKER_COMPOSE_FA.md](docs/DOCKER_COMPOSE_FA.md)
- Compatibility redirect: [docs/KUBERNETES.md](docs/KUBERNETES.md)
- Compatibility redirect: [docs/KUBERNETES_FA.md](docs/KUBERNETES_FA.md)
- Compatibility redirect: [docs/REVERSE_PROXY.md](docs/REVERSE_PROXY.md)
- Compatibility redirect: [docs/REVERSE_PROXY_FA.md](docs/REVERSE_PROXY_FA.md)

### Planning and Performance

- Performance baselines: [performance.md](docs/architecture/performance.md)

## Deployment Intent

- Primary production design: `backend-api` + `backend-worker` + `spa-bff` + `spa-web`.
- Streamlit runtime is retired from active deployment and launch paths.
- Runtime behavior is backend-segregated: frontend reads/writes and heavy jobs are backend-owned (fail-closed on backend transport failure).
- Corporate deployments (AWS/ECS/Kubernetes/VM) should follow [DEPLOYMENT.md](DEPLOYMENT.md), not embedded mode.

## Workspace tooling

This repository uses workspace manifests to make its service boundaries explicit:

- Python dependencies are declared in the root `pyproject.toml` and resolved with `uv`.
- JavaScript services are declared as npm workspaces in the root `package.json`.
- `spa-bff/` and `spa-web/` retain their own lockfiles and can still be installed independently.

From the repository root, use `uv sync --group dev` for Python tooling and `npm install` for both JavaScript services. The existing `backend_app/requirements.txt` remains a compatibility input for deployment environments while the workspace migration is phased in.

### Cross-platform task runner

The root `justfile` is the canonical cross-platform developer command surface.
Install [just](https://github.com/casey/just), then run commands from the
repository root:

```bash
just install
just test
just typecheck
just build
just check
```

### Release Promotion Path

Use this order for every pre-release and production release:

1. **CI build and test:** GitHub Actions builds the application, runs the test suite, checks API artifacts, and produces the release image.
2. **Staging deployment:** Deploy the exact commit-SHA images published to private GHCR to the Darkube staging environment.
3. **Staging evidence gate:** Run health, migration-state, authentication, BFF, and smoke checks. Do not promote an image that fails any required check.
4. **Production approval:** Require an explicit release approval after staging evidence is available.
5. **Production deployment:** Promote the same image tag to production; rebuilding between staging and production is not allowed.
6. **Rollback readiness:** Keep the previous known-good image tag and use the documented image-based rollback procedure if production verification fails.
7. **Signature verification:** Run the GitHub Actions GHCR signature verification workflow against the release manifest and require it to pass before production promotion.
8. **Production promotion:** Run the production promotion workflow with the exact manifest and staging verification run IDs, obtain the protected production approval, and deploy the resulting digest-pinned promotion record through Darkube.

Environment responsibilities:

- `CI`: build and test only.
- `Staging`: deploy candidates and collect release evidence.
- `Production`: deploy only an approved image already validated in staging.

#### Build -> release -> run contract

The release unit is an immutable, commit-addressable artifact set. CI builds
the web, BFF, backend API, and worker artifacts from one commit, using the
repository lockfiles and the workflow's pinned build inputs. Each image is
published to private GHCR with its commit-SHA identity, and the release
manifest records the image digests, source commit, signatures, and required
staging evidence.

Release promotion moves that manifest, not source code or a newly rebuilt
image. Staging and production must run the same digest-pinned image references;
production is blocked if the manifest, signature, or staging evidence does not
match. A rollback selects the previous known-good manifest and redeploys its
paired API, worker, BFF, and web digests.

Run-time configuration and secrets are injected by the target environment and
are never baked into an image. Migrations are an explicit release operation,
separate from application startup. Health checks verify the running release,
and the release record is retained with the deployment evidence.

The local development command `docker compose up -d --build` is intentionally
not a production release procedure: it creates local images and may rebuild
from the working tree. A staging or production run must pull the approved
release digests and start without rebuilding.

#### Horizontal concurrency and scaling

Horizontal concurrency is a first-class deployment lever and is adjusted per
service rather than by scaling the entire stack uniformly:

- `backend-api`: add HTTP replicas or process workers for independent request
  concurrency; keep each replica stateless and behind the service ingress.
- `backend-worker`: add worker replicas for queue throughput; job claiming is
  database-coordinated so multiple consumers do not process the same job.
- `spa-bff`: add replicas for browser-facing session and request handling; its
  session configuration must remain compatible across replicas.
- `spa-web`: add replicas when static/document serving is the bottleneck.
- `postgres`: remains a backing service; app replica counts do not imply
  database scaling and database capacity must be assessed separately.

For ordinary Docker Compose operations, use explicit service scaling; do not
assume a `deploy.replicas` value is applied by `docker compose up`:

```sh
docker compose -f deploy/docker/docker-compose.yml up -d \
  --scale backend-api=2 \
  --scale backend-worker=2 \
  --scale spa-bff=2 \
  --scale spa-web=2
```

For Kubernetes, set the corresponding Deployment replica counts or use
`kubectl scale deployment`. After changing concurrency, record service health,
queue depth, database connection usage, and latency in the deployment
evidence. Provider-specific ingress and restart behavior remains a required
external verification step.

For deployment configuration, hardening, and operational procedures, see
[DEPLOYMENT.md](DEPLOYMENT.md) and
[docs/DEPLOYMENT_OPERATIONS_GUIDE.md](docs/DEPLOYMENT_OPERATIONS_GUIDE.md).
For the factor-by-factor SaaS operations evidence ledger, see
[docs/saas/twelve-factor-evidence.md](docs/saas/twelve-factor-evidence.md).
For the GHCR image contract and Darkube registry setup, see
[deploy/ghcr/README.md](deploy/ghcr/README.md).
For production database backup and restore onboarding, see
[docs/saas/hamravesh-backup-onboarding.md](docs/saas/hamravesh-backup-onboarding.md).

### Darkube Configuration Checklist

Configure Darkube once for the private pre-release or production target:

1. Create an isolated Darkube project or namespace for the environment.
2. Add a private GHCR registry connection using a read-only package credential.
3. Create four image-based applications: `web`, `bff`, `api`, and `worker`.
4. Configure all applications with the same commit SHA:
   - Web: `ghcr.io/<owner>/<repository>/web:<commit-sha>` on port `3000`.
   - BFF: `ghcr.io/<owner>/<repository>/bff:<commit-sha>` on port `3001`.
   - API: `ghcr.io/<owner>/<repository>/backend:<commit-sha>` on port `8100`.
   - Worker: `ghcr.io/<owner>/<repository>/backend:<commit-sha>` with no HTTP port.
5. Set the API and worker commands to `python -m backend_app.run_api` and
   `python -m backend_app.worker`; keep the web and BFF image defaults.
6. Set application secrets in Darkube, including the private database URL,
   service token, signing secret, session secret, and bootstrap password.
7. Keep the API, worker, and database private; expose only the web and, when
   required by browser routing, the BFF through HTTPS.

Do not configure Darkube to clone the private GitHub repository or rebuild the
image. Deploy only commit-SHA images published by GitHub Actions. Validate the
staging deployment before promoting the same image tag to production.

### Production Database Recovery Prerequisite

Production customer-data onboarding is currently blocked pending the first
real Hamravesh backup and restore rehearsal. The repository contains the
provider-neutral contracts and evidence validator, but no provider-backed
recovery operation has been executed yet.

When the provider account is available:

1. Select the Hamravesh managed PostgreSQL database and configure its backup
   schedule, retention, encryption, and off-site policy.
2. Create an isolated, private restore target; never restore over production.
3. Execute a real restore and record only sanitized provider IDs, statuses,
   checksums, timestamps, measured RPO/RTO, and the accountable operator.
4. Run `scripts/verify_recovery_evidence.py` against the sanitized evidence.
5. Store the verified recovery evidence with the release and environment
   records before introducing persistent customer data.

The disposable pre-release environment may continue using `deferred` backup
settings with synthetic data only. Do not carry that setting into a customer
environment. See [Hamravesh production backup onboarding](docs/saas/hamravesh-backup-onboarding.md)
for the complete procedure.

For the containerized local stack:

```bash
just start
just health
just stop
```

The cross-platform `just` commands and Docker Compose are the primary operator paths. Windows launchers remain supported under `scripts/windows/` for local compatibility.

## SPA BFF

This repository includes a Node.js BFF service for browser-facing API mediation:
- Path: `spa-bff/`
- Purpose: expose only allowlisted browser-facing routes while keeping `backend-api` private/internal.
- Auth model: BFF attaches internal service token and request-signing headers server-side.

Run locally:

```bash
cd spa-bff
npm install
OKR_BACKEND_API_URL=http://127.0.0.1:8100 \
OKR_BACKEND_SERVICE_TOKEN=CHANGE_ME \
OKR_BACKEND_SIGNING_SECRET=CHANGE_ME \
npm run dev
```

Docker Compose:

```bash
docker compose -f deploy/docker/docker-compose.yml up -d --build backend-api backend-worker spa-bff
```

## SPA Web

A Next.js frontend is the primary UI:
- Path: `spa-web/`
- Uses Next.js API route proxying to BFF for `/api/backend/*` and `/api/session/*` calls.
- Unified SPA report/dashboards/check-in/admin workflow.

Run locally:

```bash
cd spa-web
npm install
npm run dev
```

Docker Compose:

```bash
docker compose -f deploy/docker/docker-compose.yml up -d --build backend-api backend-worker spa-bff spa-web
```

Compose uses the local `postgres` service from `deploy/docker/docker-compose.yml` by default when `OKR_DATABASE_URL` is not provided.
This keeps local integration aligned with production PostgreSQL behavior.

Windows quick launcher (repo root):

```bat
scripts\\windows\\run_hybrid_app.bat
```

Windows local launcher (no Docker, backend API + backend worker + BFF + SPA):

```bat
scripts\\windows\\run_hybrid_app_local.bat
```

Database URL resolution precedence for the local launcher:
`OKR_DATABASE_URL` env -> `DATABASE_URL` env -> `deploy/docker/.env`.

If startup fails, review local logs under `tmp/local-hybrid-logs/`.

## Quickstart (Local Development - SPA First)

Run commands from repository root (`okr`).

Prerequisites:

- Python 3.11+
- A reachable Postgres/Supabase database (recommended)
- Database URL set as `OKR_DATABASE_URL` (recommended) or `DATABASE_URL` (alias)

Local launcher fallback behavior:
- `scripts/windows/run_hybrid_app_local.bat` can fall back to local SQLite at `tmp/okr-local-dev.sqlite3` only when explicitly enabled.
- Control fallback with:
  - `OKR_LOCAL_DB_FALLBACK=true|false` (default: `false`)
  - `OKR_LOCAL_DB_RESET=true|false` (default: `false`, set `true` to rebuild local SQLite on launch)
- If your network blocks Postgres ports (`5432`/`6543`), verify Supabase HTTPS access over port `443`:
  - `python scripts/supabase_https_probe.py --url https://<project-ref>.supabase.co`
  - Optional API key checks use `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_ANON_KEY`.
- Explicit HTTPS-backed data-access adapter (not a local or database fallback):
   - Set `OKR_DATA_ACCESS_MODE=supabase_api`
   - Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_ANON_KEY`)
   - This selects the Supabase HTTP API for the supported operations below;
     it changes the access adapter, not the source of configuration.
   - The default `database` mode uses the environment-provided PostgreSQL URL.
   - Current scope:
     - backend startup health + `/v1/auth/login`
     - read-query kinds: `users.by_username`, `users.by_id`, `users.all`, `users.team_members`, `teams.all`, `teams.by_id`, `cycles.all`, `cycles.active`, `node.detect_type`, `node.get`, `mindmap.root`, `alignments.context`, `krs.by_cycle`, `tasks.by_cycle`, `weekly_plan.active`, `work_logs.by_task`, `work_logs.by_range`, `krs.needing_checkin`, `experiments.active_for_kr`, `experiments.for_kr`, `experiments.for_retro_window`, `retros.user`, `retros.team`, `ritual.snapshot` (consolidated Check-In snapshot via `fn_ritual_snapshot` RPC)
     - create mutations: `/v1/nodes/goal`, `/v1/nodes/objective`, `/v1/nodes/key_result`, `/v1/nodes/task`
     - update/delete mutations: `PATCH /v1/nodes/{node_type}/{node_id}`, `DELETE /v1/nodes/{node_type}/{node_id}`
     - additional mutations: `/v1/timer/start`, `/v1/timer/stop`, `/v1/check-ins`, `/v1/experiments`, `PATCH /v1/experiments/{experiment_id}`, `/v1/experiments/{experiment_id}/close`, `/v1/retrospectives`, `PUT /v1/retrospectives/{retrospective_id}/experiment-outcomes`, `/v1/weekly-plans`, `/v1/alignments`, `DELETE /v1/alignments/{edge_id}`, `/v1/objective-alignment-links`, `DELETE /v1/objective-alignment-links/{link_id}`
     - admin mutations: `/v1/users`, `PATCH /v1/users/{user_id}`, `/v1/users/{user_id}/reset-password`, `/v1/cycles`, `PATCH /v1/cycles/{cycle_id}`, `DELETE /v1/cycles/{cycle_id}`, `/v1/teams`, `PATCH /v1/teams/{team_id}`, `DELETE /v1/teams/{team_id}`
   - Unsupported read/mutation kinds currently return `501` in API mode until migrated.

Set database URL (required):

Windows PowerShell:

```powershell
$env:OKR_DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME"
```

macOS/Linux bash:

```bash
export OKR_DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME"
```

Verify environment (required):

Windows PowerShell:

```powershell
if (-not $env:OKR_DATABASE_URL -and -not $env:DATABASE_URL) { throw "Set OKR_DATABASE_URL or DATABASE_URL first." }
```

macOS/Linux bash:

```bash
test -n "$OKR_DATABASE_URL$DATABASE_URL" || { echo "Set OKR_DATABASE_URL or DATABASE_URL first."; exit 1; }
```

Run:

Windows PowerShell:

```powershell
.\scripts\windows\run_hybrid_app_local.bat
```

macOS/Linux bash:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend_app/requirements.txt
export OKR_DATABASE_URL='postgresql+psycopg2://...'
python -m backend_app.run_api &
python -m backend_app.worker &
npm --prefix spa-bff install && npm --prefix spa-bff run dev &
npm --prefix spa-web install && npm --prefix spa-web run dev
```

Optional provider health check:

```bash
python scripts/ai_provider_health_check.py
```

Success check (local):
1. SPA is reachable at `http://127.0.0.1:3000`.
2. Browser opens the login screen.
3. After login, the Atlas workspace loads.

## Quickstart (Self-Hosted Docker Compose)

Prerequisites:

- Docker Desktop (or Docker Engine + Docker Compose v2 plugin)
- `deploy/docker/.env` is present and configured
- Network access for pulling images/packages

Windows PowerShell:

```powershell
Copy-Item deploy/docker/.env.example deploy/docker/.env
python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env
docker compose -f deploy/docker/docker-compose.yml up -d --build
```

macOS/Linux bash:

```bash
cp deploy/docker/.env.example deploy/docker/.env
python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env
docker compose -f deploy/docker/docker-compose.yml up -d --build
```

Then follow full production hardening in:

- [DEPLOYMENT.md](DEPLOYMENT.md)
- [docs/DEPLOYMENT_OPERATIONS_GUIDE.md](docs/DEPLOYMENT_OPERATIONS_GUIDE.md)

Success check (self-hosted):
1. `docker compose -f deploy/docker/docker-compose.yml ps` shows services running.
2. UI is reachable at configured host/port.
3. Login works and the Atlas workspace opens.

## Security Defaults (Production)

- Keep `OKR_BACKEND_PROXY_MUTATIONS=true`.
- Keep backend API private (internal only).
- Set a strong `OKR_BACKEND_SERVICE_TOKEN`.
- Set a strong `OKR_BACKEND_SIGNING_SECRET`.
- Set a strong `OKR_BOOTSTRAP_ADMIN_PASSWORD`.
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
python scripts/perf_hotpaths.py
```

Run Playwright SPA happy-path e2e test (login -> focus map -> start timer):

Windows PowerShell:

```powershell
$env:OKR_RUN_PLAYWRIGHT_SPA_E2E="1"
python -m pytest -q tests/test_e2e_playwright_spa_login_to_atlas.py
```

macOS/Linux bash:

```bash
export OKR_RUN_PLAYWRIGHT_SPA_E2E=1
python -m pytest -q tests/test_e2e_playwright_spa_login_to_atlas.py
```

Install browser runtime once if needed:

```bash
playwright install chromium
```



