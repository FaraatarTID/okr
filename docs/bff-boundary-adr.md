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
| Route allowlisting | Exposes only approved browser routes while keeping operator/internal APIs private | Generated allowlist drift gate and OpenAPI operation-ID mapping |
| CSRF protection | Rejects state-changing browser requests that lack a valid double-submit token | CSRF request tests and [bff-security-review.md](bff-security-review.md) |
| Error shaping | Prevents internal error leakage by returning bounded error envelopes | Sanitized error contracts |

Two controls that earlier revisions of this table listed as provided were
implemented on 2026-09-29 (D4) with the limits below. Their evidence records in
[evidence/security-parity.json](evidence/security-parity.json) are dated captures
for `release-2026-09-14-bff` and still read `pending`: they describe that release,
not the current code, and are refreshed by a release capture, not by editing them.
That capture now exists for release `ef18d7f`:
[evidence/security-parity-ef18d7f.json](evidence/security-parity-ef18d7f.json) records all
six controls, including origin and rate limiting, as observed. It was taken on a disposable
local stack of the released image digests over plain HTTP, not on a production deployment
behind Nginx and TLS, so `Secure` cookies and edge-set client IPs were not observed. The
`release-2026-09-14-bff` records stay `pending` because that release did not have the
controls.

- **Origin controls, in `spa-web`, not `spa-bff`.** The browser never reaches the
  BFF; it reaches the `spa-web` route handlers, and `proxyToBff` forwards a fixed
  header list that omits `Origin`. The decision is therefore made in
  `spa-web/src/lib/origin-guard.ts`, applied to `POST /api/session/login`,
  `POST /api/session/logout` and every non-GET/HEAD call through
  `/api/backend/*`. `Sec-Fetch-Site` decides when present (only `same-origin` and
  `none` pass); otherwise a present `Origin` must match the request host
  (`X-Forwarded-Host`, then `Host`); with neither header the caller is not a
  browser and is allowed, so probes and curl keep working. It answers 403
  `INVALID_ORIGIN`. Limits: it is not an allowlist of extra origins, scheme is
  not compared, and `spa-bff` itself still reads neither header, so a caller who
  reaches the BFF directly is outside this control (the BFF is not exposed to the
  browser). CSRF double-submit remains a separate, second layer on actor-scoped
  routes; login has no CSRF token because it is what issues it.
- **Rate limiting at the browser edge, as a backstop only.** `spa-bff/src/rate-limit.ts`
  applies an in-process fixed window per client address to `POST /session/login`
  and `POST /api/backend/v1/auth/login` (default 60 per 60 s) and to
  `/session/me` and `/session/logout` (default 600 per 60 s), answering 429
  `RATE_LIMITED` with `Retry-After`. The key is the trusted `X-OKR-Client-IP`
  when it parses as an IP, else the socket peer; `request.ip` is never used
  because `trustProxy` derives it from `X-Forwarded-For`. It is **not** the
  authoritative control: state is per process, so with N replicas the effective
  ceiling is N times the configured value and it resets on restart, and the key
  map is capped (`BFF_RATE_LIMIT_MAX_KEYS`) so an over-cap spray evicts the oldest
  key. Authenticated `/api/backend/*` traffic is not limited here. The shared,
  authoritative limits remain the backend's (`OKR_BACKEND_RATE_LIMIT_*` and the
  login lockout); the BFF may not hold shared state (`check_spa_bff_boundaries.py`).

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

The canonical evidence capture command is:

```text
python scripts/slo_probe.py \
  --base-url https://<browser-origin> \
  --username <synthetic-user> \
  --password <synthetic-password> \
  --output evidence/bff-slo.json
```

The JSON artifact contains only endpoint metadata, timings, status summaries,
and pass/fail results; it does not write credentials, cookies, or response
bodies. Capture equivalent artifacts for each candidate topology and retain
them with the release evidence. A topology decision remains open until the
artifacts include latency/error comparisons and a documented restart/rollback
rehearsal.

Compare two captured runs with:

```text
python scripts/compare_topology_evidence.py \
  evidence/bff-slo.json \
  evidence/direct-api-slo.json \
  --baseline-resources evidence/bff-resources.json \
  --candidate-resources evidence/direct-api-resources.json \
  --resource-map evidence/resource-map.json \
  --output evidence/topology-comparison.json
```

The comparison reports per-SLO absolute and relative changes, but deliberately
returns `human_review_required`; lower latency alone is not sufficient to
remove the browser security boundary.

After the comparison, record the non-latency evidence in a review manifest and
validate it with:

```text
python scripts/validate_topology_review.py evidence/topology-review.json
```

The manifest must include passed, linked evidence and a summary for
`security_parity`, `failure_isolation`, `resource_overhead`, and
`rollback_rehearsal`. This prevents a latency-only result from being treated
as approval to remove the BFF.

For the resource-overhead category, capture a sanitized Compose snapshot with:

```text
just topology-resources evidence/compose-resources.json
```

The snapshot records container names, CPU percentages, and memory usage only; it
does not retain container IDs, environment variables, logs, or application
payloads.

Record restart rehearsals with the required scenarios
`bff_unavailable_api_reachable`, `api_unavailable_bff_reports_dependency_failure`,
and `worker_unavailable_api_remains_ready`. Validate the resulting manifest with
`python scripts/validate_failure_isolation.py`; each scenario must link its
sanitized observation artifact and be explicitly marked `passed`.

Record security-parity observations for session-cookie protection, CSRF and
origin controls, actor binding, request signing, route allowlisting, and rate
limiting. Validate the manifest with `just topology-security-review
evidence/security-parity.json`; every control must link its sanitized artifact
and be explicitly marked `passed`.

Validate rollback evidence with `just topology-rollback-review
evidence/rollback-rehearsal.json`. It must identify the last-known-good and
candidate releases, record restoration duration, verify data integrity, and
link the sanitized rehearsal artifact.

Resource snapshots should be compared alongside the SLO artifacts during the
review. The comparison tool reports CPU deltas and preserves the before/after
memory strings, allowing the operator to record resource overhead without
claiming that a single sample is a capacity benchmark.

When container names differ between topologies, `resource-map.json` must map a
logical role to the corresponding baseline and candidate containers, for
example: `{ "api": { "baseline": "bff-api-1", "candidate": "direct-api-1" } }`.

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

- BFF policy check passed: `npm run check:allowlist` reports 44 routes up to date, each mapped to a generated OpenAPI operation ID.
- The package does not define `npm run check`; the intended allowlist control is `npm run check:allowlist`.
- BFF test suite passed: `npm --prefix spa-bff test` completed 16 test files and 233 tests successfully (measured 2026-09-29; re-measure rather than trust this figure, because it changes with every added test).
- The cross-layer OpenAPI contract workflow and CI gates are documented in [openapi-contract-synchronization.md](openapi-contract-synchronization.md).
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

The backend exposes operator-only `/control-plane/environments` list and detail
routes as an ephemeral, process-local inventory. They do not read the operator
CLI state file and are not an authoritative environment or lifecycle record.
Lifecycle changes remain in the explicit file-backed operator CLI workflow; the
API has no lifecycle-event write route. The separate SQL-backed fleet rollout
read remains operator-only. None of these routes is a customer-domain API or
may proxy, query, or mutate goals, users, teams, or other OKR records. Customer
traffic continues through the BFF to the canonical backend application
boundary.
