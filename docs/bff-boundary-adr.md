# ADR: BFF Responsibility and Topology

Documentation HQ: [README](../README.md)

Status: `IN-PROGRESS` for P0-03 (repository controls verified; provider evidence open).

## Context

The current deployment topology contains a Next.js web application, a TypeScript BFF, a Python backend API, and a background worker. The pre-SaaS architecture needs a clear boundary before SaaS-specific tenancy, authentication, and operational concerns are added.

The BFF must not become a second domain layer. The backend API remains the canonical owner of business rules and application behavior, as proposed in [architecture-boundaries.md](architecture-boundaries.md).

## Working decision

Retain `spa-bff` as a separate deployable for the pre-SaaS baseline. Limit it to browser-facing edge responsibilities that are explicit in its contract:

- session and browser security mediation;
- request validation and route mediation at the browser boundary;
- response shaping required by the web client;
- correlation, rate, and edge observability concerns;
- forwarding requests to the canonical backend API.

Business rules, persistence access, migrations, and cross-client application use cases remain in the backend package and shared service/domain layers.

The repository decision and controls are verified: the BFF remains a separate deployable because it provides a controlled browser-security boundary. Operational closure remains open only for provider-backed deployment, rollback, and production measurement evidence.

## BFF value test

The BFF is justified by security and browser-boundary responsibilities, not by
the mere fact that the repository has a frontend. Each BFF capability must map
to a concrete value and must not duplicate backend business rules:

| Capability | Value provided by `spa-bff` | Evidence to preserve |
|---|---|---|
| HTTP-only session cookies | Keeps browser session material out of frontend JavaScript | Session tests and secure-cookie configuration |
| Authentication bridging | Converts browser login/session state into authenticated internal API calls | Session and backend-auth contract tests |
| Actor binding | Prevents clients from selecting another actor through request payloads or headers | Actor-rewrite rejection tests |
| Request signing and service token | Authenticates the BFF-to-backend hop and detects tampering | Signing and replay-protection tests |
| Route allowlisting | Exposes only approved browser routes while keeping operator/internal APIs private | Generated allowlist drift gate |
| CSRF and origin controls | Protects state-changing browser requests at the edge | BFF security review and request tests |
| Rate limiting and error shaping | Controls browser-facing abuse and prevents internal error leakage | BFF policy tests and sanitized error contracts |

The BFF must not become a redundant pass-through layer. New BFF code requires
an entry in this matrix or an approved architecture decision explaining its
browser-edge value. Domain rules, persistence, migrations, and cross-client
use cases remain backend responsibilities.

## Topology review checkpoint

Before removing, merging, or thinning the BFF, capture comparable evidence for
the separate-service and proposed simplified topologies:

- p95 BFF-to-backend latency and representative error rate;
- CPU and memory overhead under representative single-tenant traffic;
- failure isolation when the BFF, API, worker, or database is restarted;
- security parity for sessions, actor binding, signing, CSRF, allowlisting, and
  rate limiting;
- independent deployment and rollback behavior for the web, BFF, API, and
  worker.

No simplification is a supported deployment profile until the replacement
passes those checks and receives a new ADR decision. Co-location on one host
with separate service processes remains the lower-risk optimization.

## Deployment decision and small-installation runbook

Separate `spa-bff`, backend API, worker, and web deployments are the production
default. The BFF remains the only browser-facing application boundary; the API,
worker, and database stay private. This is the topology represented by the
Compose and Darkube deployment contracts.

For a small single-tenant installation, services may be **co-located on the
same approved host or provider node** only when the platform still runs them as
four independently managed containers or services. Co-location is a placement
optimization, not a new application mode. It must satisfy every condition
below before deployment:

- **Network:** web reaches the BFF through the approved HTTPS origin; BFF reaches
  the API through a private service address; API and worker reach only the
  private database. The API and database receive no public ingress.
- **Health:** API and BFF retain independent `/healthz` checks; the worker has
  an independent startup/status signal; each service has its own restart policy
  and readiness gate. A healthy BFF must not mask an unhealthy API or worker.
- **Security:** preserve BFF session, cookie, CSRF, actor-binding, and request-
  signing controls; keep backend and BFF secrets distinct; enforce backend
  authorization independently; do not expose a direct browser-to-API escape
  route or use shared filesystem/database credentials as a shortcut.
- **Observability:** collect separable logs, deployment identities, health
  results, resource usage, and correlation identifiers for each service. An
  incident must be diagnosable as a BFF, API, worker, or database failure.
- **Operations:** deploy, restart, scale, and roll back the BFF and backend
  artifacts independently, while keeping API and worker on the same backend
  image commit. Verify the complete web-to-BFF-to-API path after every change.

Do not merge the BFF into the Python process, let it access persistence directly,
remove the worker, or replace the four-service contract with an undocumented
provider-specific topology. If the target platform cannot provide the private
networking, independent health checks, separate secrets, service-level logs, or
independent rollback required above, use the standard separate deployment and
record the co-location option as unavailable.

## Topology

```text
spa-web --> spa-bff --> backend_app API --> domain/services --> adapters/database
                                      |
                                      +--> backend-worker
```

The BFF communicates with the backend through a documented HTTP contract. It must not import Python modules or connect directly to the database.

## Decision criteria

The BFF boundary can be revisited when all of the following are evidenced:

- browser-only responsibilities are enumerated and stable;
- BFF-to-API latency and failure behavior are measured;
- authentication and session ownership are unambiguous;
- direct browser-to-API access has been assessed for security and operability;
- removing or thinning the BFF has a tested rollback path;
- the resulting topology does not duplicate business logic.

## Rejected alternatives for now

### Merge BFF behavior into the Python API immediately

Rejected for the current phase because it would combine browser-edge concerns with backend assembly before the existing responsibilities and migration path are fully traced.

### Let the BFF access persistence directly

Rejected because it would create a second backend boundary, duplicate authorization decisions, and weaken the domain and adapter ownership proposed in P0-01.

### Make the BFF a permanent general-purpose application layer

Rejected because it would encourage business logic duplication and make future clients depend on browser-specific behavior.

## Ownership and failure behavior

| Concern | Owner | Required behavior |
|---|---|---|
| Browser session and edge security | `spa-bff` | Fail closed and return a client-safe error |
| Business authorization | Backend API and application services | Enforce independently of the BFF |
| Domain invariants | `src/domain` | Remain client-independent |
| Persistence availability | Backend adapters and database | Surface readiness separately from BFF liveness |
| BFF unavailable | Deployment/orchestration layer | Web client shows bounded failure; API remains independently diagnosable |

## Evidence required for closure

- BFF policy check passed: `npm run check:allowlist` reports 44 routes up to date.
- The package does not define `npm run check`; the intended allowlist control is `npm run check:allowlist`.
- BFF test suite passed: `npm test` completed 7 test files and 65 tests successfully.
- Initial live health baseline captured on 2026-08-31: backend HTTP 200 in approximately 1146 ms and BFF HTTP 200 in approximately 7 ms for single local requests. This is a local baseline sample, not a production performance conclusion.
- Route and responsibility inventory for `spa-bff/src/server.ts`.
- API contract mapping for every BFF-to-backend call.
- Latency and error-budget measurement for the BFF hop.
- Security review of session, signing, and authorization behavior.
- [bff-security-review.md](bff-security-review.md) captures the repository-grounded control review and residual risks.
- Container and local readiness evidence for the BFF.
- Rollback rehearsal showing the last-known-good BFF and API pair.

P0-03 should move to `VERIFIED` only when this evidence is linked from the architecture status ledger.

## Control-plane boundary

The backend exposes an operator-only `/control-plane/environments` boundary for
environment inventory and lifecycle audit metadata. It is not a customer-domain
API and must not proxy, query, or mutate goals, users, teams, or other OKR
records. Customer traffic continues through the BFF to the canonical backend
application boundary.
