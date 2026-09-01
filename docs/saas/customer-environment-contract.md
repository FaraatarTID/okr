# Customer Environment Contract

Documentation HQ: [README](../README.md)

Status: Phase 1 contract, v1

This contract describes one customer environment for the approved
single-tenant SaaS model. It defines identity, configuration, health, backup
metadata, and lifecycle state. It does not provision infrastructure, route
customer traffic, add tenant identifiers, enable PostgreSQL RLS, or run
migrations.

## Manifest

`src.saas.environment_contract.EnvironmentManifest` is the typed source of
truth. Only contract version `v1` is supported. Its fields are:

| Field | Meaning |
| --- | --- |
| `contract_version` | Manifest schema version, currently `v1`. |
| `environment_id` | Stable identifier for one isolated application/database environment. |
| `customer_id` | Stable enterprise owner identifier. |
| `deployment_profile` | `on_premise`, `single_tenant_saas`, or external `control_plane`. |
| `application_version` | Immutable application artifact/version selected for the environment. |
| `database_resource_id` | Opaque provider resource identifier for the dedicated SaaS database; never a URL or credential. `database_target` is a temporary input/read alias only. |
| `health_endpoint` | Operator-facing liveness/readiness endpoint, defaulting to `/healthz`. |
| `backup_policy` | Typed metadata describing provider, schedule, and retention; execution is a later operations concern. |
| `lifecycle_state` | Current state from the lifecycle state machine. |
| `control_plane_owner` | Optional non-empty owning control-plane identifier for a SaaS-managed environment; forbidden for `on_premise`. |
| `idempotency_key` | Stable key for a requested lifecycle operation. |

SaaS manifests must name a non-empty dedicated database target and therefore
report `is_isolated=True`. The control plane is not a deployment profile in
this contract: it is an external management boundary, represented only by
optional `control_plane_owner` metadata on a SaaS environment. On-premise
manifests cannot claim that ownership. Unknown profiles, lifecycle states,
events, and contract versions are rejected. Empty identity,
application-version, idempotency, or supplied operational metadata values are
also rejected.

## Lifecycle transitions

The implementation exposes `transition(state, event)`. It returns the next
state for a legal event and `None` for every illegal event. In particular,
`RETIRED` is terminal and cannot be activated again.

| Current state | Event | Next state |
| --- | --- | --- |
| `PROVISIONING` | `COMPLETE_PROVISIONING` | `READY` |
| `PROVISIONING` | `MARK_DEGRADED` | `DEGRADED` |
| `PROVISIONING` | `RETIRE` | `RETIRED` |
| `READY` | `SUSPEND` | `SUSPENDED` |
| `READY` | `BEGIN_UPGRADE` | `UPGRADING` |
| `READY` | `MARK_DEGRADED` | `DEGRADED` |
| `READY` | `RETIRE` | `RETIRED` |
| `SUSPENDED` | `ACTIVATE` | `READY` |
| `SUSPENDED` | `RETIRE` | `RETIRED` |
| `UPGRADING` | `COMPLETE_UPGRADE` | `READY` |
| `UPGRADING` | `MARK_DEGRADED` | `DEGRADED` |
| `UPGRADING` | `RETIRE` | `RETIRED` |
| `DEGRADED` | `RECOVER` | `READY` |
| `DEGRADED` | `SUSPEND` | `SUSPENDED` |
| `DEGRADED` | `BEGIN_UPGRADE` | `UPGRADING` |
| `DEGRADED` | `RETIRE` | `RETIRED` |

## Idempotency and operator-visible failures

Lifecycle requests use a non-empty `idempotency_key` to make retries refer to the same
requested operation. A later provisioning task must persist the key with the
environment operation and converge on one environment rather than allocate a
duplicate.

When `backup_policy` is supplied, its provider and schedule are required to be
non-empty. The default `deferred` values document that backup execution is not
yet implemented for the disposable pre-SaaS environment.

Validation failures are operator-visible before any infrastructure action:
they identify the rejected manifest field or illegal transition. A missing
database target, unsupported deployment profile, empty identity/version,
on-premise control-plane claim, and any transition absent from the table are
fail-closed conditions. A `DEGRADED` state is an operational signal, not an
implicit authorization to bypass health checks.
