Documentation HQ: [README](../README.md)

# Documentation Lifecycle

This registry keeps enterprise documentation discoverable without presenting
historical or compatibility material as current operational guidance.

## Lifecycle categories

| Category | Meaning | Maintenance rule |
| --- | --- | --- |
| Canonical | Current source of truth for a product, architecture, or workflow | Keep linked from Documentation HQ and review when behavior changes |
| Operational | Current deployment, configuration, troubleshooting, observability, or recovery guidance | Record an owner and review date; update before operational changes |
| Compatibility | Retained redirect for existing external or historical links | Do not duplicate guidance; point to the canonical document |
| Historical | Closed plan, decision record, or evidence of completed work | Retain for traceability, but do not describe it as current procedure |
| Template | Reusable governance or rollout artifact | Keep separate from product behavior documentation |

## Current registry

| Area | Category | Canonical entry |
| --- | --- | --- |
| System architecture and code ownership | Canonical | `ARCHITECTURE.md`, `CODEBASE_MAP.md` |
| Architecture execution and evidence | Canonical | `ARCHITECTURE_BACKLOG.md`, `docs/architecture-status.md`, `docs/ARCHITECTURE_DELIVERY_SYSTEM.md` |
| Enterprise SaaS strategy | Canonical | `ENTERPRISE_SAAS_ROADMAP.md` |
| Enterprise deployment | Operational | `DEPLOYMENT.md` |
| Runtime configuration | Operational | `docs/CONFIG_REFERENCE.md` |
| Incident troubleshooting | Operational | `docs/TROUBLESHOOTING.md` |
| Observability and incident response | Operational | `docs/OBSERVABILITY_AND_RUNBOOKS.md` |
| Recovery and retention drills | Operational | `docs/OPS_READINESS_AND_RECOVERY_GUIDE.md` |
| Product and role workflows | Canonical | `docs/USER_GUIDE.md`, `docs/MANAGER_PLAYBOOK.md`, `docs/ADMIN_GUIDE.md` |
| Strategy and rollout governance | Canonical | `docs/OKR_ROLLOUT_GUIDE.md`, `docs/OKR_BAU_BOUNDARY_GUIDE.md` |
| Consolidated deployment redirects | Compatibility | `docs/DEPLOYMENT_OPERATIONS_GUIDE.md`, `docs/DOCKER_COMPOSE.md`, `docs/KUBERNETES.md`, `docs/REVERSE_PROXY.md` |
| Completed implementation record | Historical | `docs/PLAN_PER_MANAGER_ACTIVE_CYCLES.md` |
| Previous reliability strategy | Historical | `docs/archive/ENTERPRISE_RELIABILITY_ROADMAP_2026-08-31.md` |
| Reusable rollout artifacts | Template | `docs/templates/` |

The Persian documents mirror the relevant English canonical or operational
entry. Compatibility redirects remain only while their links have practical
value. Obsolete alpha or superseded guidance should be removed or moved out of
the current index.
