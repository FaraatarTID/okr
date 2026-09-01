# ADR: BFF Responsibility and Topology

Documentation HQ: [README](../README.md)

Status: `IN-PROGRESS` for P0-03.

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

This is a working decision, not a final closure. The separation is retained because the repository already deploys the BFF independently and because it provides a controlled boundary for browser-specific concerns while the SaaS topology is still being defined.

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
