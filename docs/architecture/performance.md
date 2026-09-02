# Performance Baselines

Documentation HQ: [README](../../README.md)

This document tracks performance baselines and query-budget guardrails for critical hot paths.

## Atlas Load-Time Recovery Status

The reported multi-second page load was investigated and the local
Supabase-mode performance blocker is now closed for the validated login and
read/query gate. The following
code-level causes have been checked or fixed:

- Atlas hierarchy reads are set-based rather than ORM lazy-loading traversal.
- Ritual mode no longer performs one experiment request per key result.
- The BFF is already a backend payload pass-through for this path.
- Independent bootstrap reads are already parallelized where their inputs are
  independent.
- Initial Atlas snapshot loading no longer waits 200 ms before starting.
- Raw AI analysis is limited to Atlas inspector mode; other views use derived
  fields only.

The next evidence required is a browser waterfall correlated with backend
timings, database query count, data-access strategy, fallback queueing, circuit
state, serialization time, and client rendering time. No additional broad
optimization should be accepted without that correlation.

### Read-path `Server-Timing` attribution

Read responses now expose a safe `Server-Timing` header. The backend reports
`app;dur` for backend processing and `data;dur` for measured upstream data
access. The BFF preserves those values and appends `bff-upstream;dur` for its
backend HTTP hop. Values contain durations only; payloads, query text,
credentials, actor names, and identifiers are not logged or emitted.

This makes a browser waterfall distinguish backend/data time from total BFF
request time without changing the SLO probe or asserting a performance target.

## Deterministic end-to-end trace contract

Use `scripts/diagnose_page_load.py` with a JSON artifact containing one
`total_duration_ms` value and mutually exclusive `spans` for `browser`, `bff`,
`backend`, and `database`. The tool computes accounted time, explicitly labels
the remainder as `unattributed`, and identifies the first layer to investigate.
It deliberately does not infer query, pooling, or serialization causes.

The checked-in example at `tests/fixtures/page_load_trace.json` represents a
10-second load with only 34% attributed to measured layers. Run it with:

```bash
python scripts/diagnose_page_load.py tests/fixtures/page_load_trace.json
```

Replace the example with sanitized measurements from a browser waterfall and
correlated service logs when investigating a real incident. The regression
contract is `tests/test_page_load_diagnostics.py`.

## Current Baselines (Measured February 16, 2026)

| Path | Median Time | P95 Time | Observed Queries | Query Budget |
| --- | --- | --- | --- | --- |
| `get_leadership_metrics` | 10.09 ms | 10.21 ms | 3 | 4 queries |
| `get_krs_needing_checkin` | 1.17 ms | 1.18 ms | 1 | 2 queries |
| `get_hours_by_goal` | 0.77 ms | 0.78 ms | 1 | 1 query |

## Local reproduction attempt (September 2, 2026)

The repository hot-path benchmark was rerun against a fresh local SQLite
database seeded with 8 users, 40 goals, 120 objectives, 480 key results, and
2,880 tasks. It produced:

| Path | Median | P95 | Queries |
| --- | ---: | ---: | ---: |
| `get_leadership_metrics` | 1.61 ms | 1.79 ms | 3 |
| `get_krs_needing_checkin` | 0.72 ms | 0.74 ms | 1 |
| `get_hours_by_goal` | 0.78 ms | 0.80 ms | 1 |

This does not reproduce the reported approximately 10-second browser page
load. It also does not prove end-to-end readiness: the benchmark excludes the
browser, Next.js rendering, BFF transport, backend network hop, production
connection pool, and provider database latency. No query, index, or pooling
change should be made based on the benchmark alone.

The local Compose stack was reachable on September 2, 2026: `spa-web`,
`spa-bff`, `backend-api`, `backend-worker`, and `postgres` were all running,
with the API and database reporting healthy status. This removes Docker
availability as a blocker for local evidence collection, but does not replace
the authenticated SLO probe or a browser waterfall.

### Authenticated local SLO evidence
### Final corrected authenticated local SLO evidence

On September 2, 2026, the disposable `slo-probe` account authenticated through
the browser-facing stack. The final corrected probe reported:

| Check | Result | Interpretation |
| --- | --- | --- |
| Login p95 | 2.936 s, 10/10 successful | Within the 3.0 s target; pass. |
| Browser-port healthz | HTTP 200 in 0.005 s | Pass. |
| Read/query p95 | 3.611 s, 10/10 successful | Above the 1.5 s target; this remains the real service-path blocker. |
| Weekly-plan mutation | 10/10 errors | Failing functional probe; not a valid mutation latency signal. |
| Snapshot median | 2.387 s, 0/6 successful | Failing functional probe and above the expected latency target. |
| Job queue | Skipped; submission returned HTTP 403 | No queue-lag measurement was obtained. |

The account was disabled through the application after the run. This evidence
does not claim physical deletion. The read/query measurement remains the
authoritative local performance blocker. The dedicated-Postgres fixture now
seeds the active cycle and owned OKR graph required by the probe; the probe
also passes the resolved cycle and user identifiers into its read and snapshot
requests. Empty weekly-plan, retrospective, work-log, and experiment sections
are valid fixture results and do not require additional rows.

The repository finding that caused the provisioning/authentication failure was
fixed: Supabase stores uppercase role labels (`ADMIN`, `MANAGER`, `MEMBER`),
while the application domain uses lowercase `UserRole` values. API-mode reads
and the ORM enum boundary now normalize/map those labels correctly.
The measured container was configured with `OKR_DATA_ACCESS_MODE=supabase_api`,
so these timings include the remote Supabase HTTPS/pooler path and are not yet
a dedicated-Postgres baseline. Repeat the same gate in the supported dedicated
database mode before approving customer forks, while retaining this Supabase
result as a real slow-path finding.

### Latest post-optimization Supabase probe

After the bounded Supabase read-path optimizations, the disposable `slo-probe`
account was used for a fresh authenticated probe. The account was disabled
immediately after the run.

| Check | Result | Interpretation |
| --- | --- | --- |
| Login p95 | 2.674 s, 10/10 successful | Within the 3.0 s target; pass. |
| Browser-port healthz | HTTP 200 in 0.010 s | Pass. |
| Read/query p95 | 2.543 s, 10/10 successful | Above the 1.5 s target; fail, but faster than the prior 2.738 s result and the 3.559 s baseline. |
| Snapshot median | 2.239 s, 0/6 successful | Functional probe did not produce successful snapshots. |
| Weekly-plan mutation | 10/10 errors | Failing functional probe; not a valid mutation latency signal. |
| Job queue | Skipped; submission returned HTTP 403 | No queue-lag measurement was obtained. |

The latest read/query timing attribution was `app_p50=2137.1 ms`,
`bff-upstream_p50=2417.0 ms`, and `data_p50=279.5 ms`. The lifecycle
instrumentation below identifies the dominant portion of that residual as the
service-access dependency dispatch rather than response serialization.
The read/query blocker remains because the Supabase API-mode path is still
above its 1.5-second target. This result continues to support the
dedicated-PostgreSQL comparison as the relevant baseline for customer forks.
The disposable account was disabled immediately after the probe; no active
probe account remains.

### Latest detailed live Supabase timing

The latest live Supabase probe captured the following detailed timing evidence.
The disposable `slo-probe` account was disabled after the probe; no active
probe account remains.

| Check | Result | Interpretation |
| --- | --- | --- |
| Login p95 | 2.574 s, 10/10 successful | Within the 3.0 s target; pass. |
| Browser-port healthz | HTTP 200 in 0.010 s | Pass. |
| Read/query p95 | 2.685 s, 10/10 successful | Above the 1.5 s target; fail. |
| Snapshot median | 2.210 s, 0/6 successful | Functional probe did not produce successful snapshots. |
| Weekly-plan mutation | 10/10 errors | Failing functional probe; not a valid mutation latency signal. |
| Job queue | Skipped; submission returned HTTP 403 | No queue-lag measurement was obtained. |

The prior read timing phases were:

| Phase | P50 |
| --- | ---: |
| `actor` | 0.0 ms |
| `scope` | 137.1 ms |
| `handler` | 137.1 ms |
| `data` | 274.5 ms |
| `app` | 2,115.9 ms |
| `bff-upstream` | 2,413.2 ms |

### Framework lifecycle attribution

The next live probe added request-local spans for `POST /v1/read/query` around
service-access dependency dispatch, route handler invocation, response-model
serialization/framework remainder, and middleware completion. The latest
sanitized p50 values were:

| Phase | P50 |
| --- | ---: |
| `dependency` | 2,131.4 ms |
| `handler` | 420.7 ms |
| `data` | 279.5 ms |
| `serialization` | approximately 0 ms residual |
| `completion` | 2,412.4 ms |

This attributes the unexplained approximately two seconds to service-access
dependency dispatch. Response-model serialization is not the dominant cause.
The dependency span is intentionally measured at the framework boundary and
does not expose credentials, payloads, actor names, or query text. The next
optimization slice should profile the service-access dependency itself before
changing application handlers or schemas.

### Service-access dependency finding and fix

The service-access dependency was traced through `require_service_access` to
the shared rate-limit store. Token comparison, request-signature verification,
and nonce validation are local or cryptographic operations; the remote work was
the database-backed atomic rate-limit transaction. The running configuration
used `NullPool`, so every request opened a new PostgreSQL connection to the
remote security-state database before executing that transaction.

The backend default now uses the existing bounded SQLAlchemy pool (size `5`,
maximum overflow `5`). This preserves the atomic counter update, distributed
rate limiting, replay protection, and fail-closed behavior. An explicit
`OKR_BACKEND_SECURITY_STATE_DB_USE_NULL_POOL=true` override remains available
for deployments that intentionally require it. The focused security-state and
ingress regression suite passed (`23` tests), and the rebuilt running backend
reports `QueuePool` with size `5`.

This fixes the confirmed connection-churn mismatch in the repository/runtime
default. A fresh authenticated Supabase probe is still required to quantify
the p50 improvement; the final validated result is recorded below.

### Final validated Supabase-mode pooling result

After switching the security-state database from per-request `NullPool`
connections to the bounded `QueuePool`, the final local Supabase-mode gate was
run on September 2, 2026 with the disposable `slo-probe` account. The account
was disabled immediately after the probe; no active disposable account
remains.

| Check | Result | Interpretation |
| --- | --- | --- |
| Login p95 | 1.392 s, 10/10 successful | Within the 3.0 s target; pass. |
| Read/query p95 | 1.396 s, 10/10 successful | Within the 1.5 s target; pass. |
| Snapshot median | 1.160 s, 0/6 successful | Fixture/functional result remains open; not a passing snapshot gate. |
| Weekly-plan mutation | 10/10 errors | Mutation fixture/contract result remains open. |
| Job queue | Unsupported; HTTP 403 | Provider/data-access boundary remains open; no queue-lag measurement was obtained. |

The final read timing attribution was `dependency_p50=976.8 ms`,
`app_p50=980.3 ms`, `data_p50=313.8 ms`, and
`bff-upstream_p50=1303.0 ms`. These measurements close the performance blocker
for this local Supabase-mode login/read gate. Snapshot and mutation fixture
coverage remains open, as do provider-dependent Darkube deployment evidence
and the application rollback rehearsal. Database recovery remains a separate
production prerequisite.

### Supabase API-mode contract boundary

Supabase API mode is not a complete replacement for the application database.
The weekly-plan mutation now enforces the actor's target-user scope before its
REST write. Durable async jobs remain explicitly unavailable in this mode:
`async_job` and worker state are SQLAlchemy-backed, so job endpoints return HTTP
503 instead of silently reading or writing a different local database. Job SLO
measurements must therefore use dedicated PostgreSQL/database mode until a
remote durable job-store contract is implemented and verified.
The SLO probe recognizes this explicit `503` boundary as unsupported rather
than treating it as queue-lag evidence; unexpected submission failures in
database mode remain failures.

Fork-readiness remains blocked until one trace correlates the reported page
load across these boundaries:

1. Browser request waterfall and client rendering/hydration time.
2. BFF request duration and backend upstream duration.
3. Backend application timing, serialization time, and query count.
4. Database connection acquisition time and statement duration.
5. Data-access mode, fallback/circuit state, and response payload size.

Required capture command for the local stack, once a synthetic test account is provisioned:

```bash
python scripts/slo_probe.py --base-url http://127.0.0.1:3000 --username <synthetic-user> --password <synthetic-password>
```

The credentials must come from environment-driven test fixtures or protected
runtime configuration and must not be committed.

### Dedicated PostgreSQL disposable fixture

For a local apples-to-apples comparison, start a separate Compose project in
direct database mode and seed only its disposable PostgreSQL volume. The helper
is additive-only: it never updates, deletes, truncates, or resets existing rows,
and it refuses Supabase API mode.

PowerShell example:

```powershell
# Use the separate Compose project/ports described in the dedicated-Postgres
# runbook; do not source deploy/docker/.env.
$env:OKR_DATA_ACCESS_MODE = "database"
$env:OKR_DATABASE_URL = "postgresql+psycopg2://okr:okr_dev_password@127.0.0.1:15433/okr"
$env:OKR_BOOTSTRAP_ADMIN_PASSWORD = "<strong-local-only-password>"
python scripts/seed_performance_fixture.py --confirm-disposable
python scripts/slo_probe.py --base-url http://127.0.0.1:13000 --username perf-fixture-admin --password $env:OKR_BOOTSTRAP_ADMIN_PASSWORD
```

Use this only after the isolated dedicated-Postgres Compose project is running;
Compose startup applies the schema migrations; the seed helper only inserts
missing fixture rows after the schema is ready. Do not source the ignored
Supabase-backed `deploy/docker/.env`. The password is environment-driven and is
never printed by the seed helper.

The helper's active cycle, fixture admin, and owned hierarchy with ACTIVE
objective/key-result lifecycle states are the minimum data contract for
`krs.by_cycle` and `ritual.snapshot`. The snapshot may legitimately return
empty weekly-plan, retrospective, work-log, and experiment sections; the
active key result is required so the Check-In read is representative. If an
older fixture has DRAFT rows, the helper refuses to alter them and instructs
the operator to use a fresh disposable database. Do not point this seed command
at Supabase API mode or a non-disposable database.

### Supabase snapshot fixture opt-in

The SLO probe does not create provider data by default. It selects an accessible
active cycle when one exists; otherwise SLO-5 is reported as unavailable rather
than sending an invalid `cycle_id=0` request. For an explicitly disposable
Supabase or live-stack probe, the operator may opt in to a probe-owned cycle:

```powershell
python scripts/slo_probe.py `
  --base-url http://127.0.0.1:3000 `
  --username slo-probe `
  --password $env:SLO_PROBE_PASSWORD `
  --prepare-snapshot-fixture `
  --confirm-disposable
```

The two flags are intentionally required together. The probe creates an active
cycle only after the authenticated user has no accessible active cycle, binds
it to that user's ID, validates the returned title/owner/active state, and
deletes only the cycle ID created by that invocation in a `finally` cleanup.
Disposable cycle creation is restricted to an authenticated admin probe. Before
creation, the probe requires a successful `cycles.all` response with no active
cycles; if any active cycle is visible, or the provider cannot return the full
list, creation is refused. This is necessary because the application cycle
creation invariant may deactivate existing active cycles. Existing cycles are
never activated, deactivated, or deleted by the probe. If creation or validation
fails, SLO-5 remains a failed prerequisite and no cleanup target is retained.
The disposable account itself remains the operator's responsibility to remove
after the run.

### Final dedicated-PostgreSQL comparison evidence

On September 2, 2026, the same disposable performance probe was run against
the isolated dedicated-PostgreSQL Compose stack. The latency checks passed:

| Check | Dedicated PostgreSQL result | Status |
| --- | --- | --- |
| Login p95 | 0.311 s, 10/10 successful | Pass |
| Browser-port healthz | 0.022 s | Pass |
| Read/query p95 | 0.075 s, 10/10 successful | Pass |
| Snapshot median | 0.127 s, 6/6 successful | Pass |
| Weekly-plan mutation | 10/10 errors | Separate contract/authorization gap |
| Job queue | Skipped; submission returned HTTP 403 | Separate contract/authorization gap |

Compared with the Supabase API-mode run above, dedicated PostgreSQL reduced
login p95 from 2.936 s to 0.311 s and read/query p95 from 3.611 s to 0.075 s.
This controlled comparison isolates the remote Supabase API/HTTPS path as the
dominant measured latency contributor for these requests. It does not establish
that every SLO passes: weekly-plan mutation and job-queue checks remain
unresolved contract/authorization gaps, independent of the latency result.

### Supabase read-path optimizations

The Supabase read path now reuses the admin scope's single `users.all` response
when deriving both owner and administrator scopes, avoiding a duplicate remote
request on every authenticated read. HTTP client initialization is also
serialized so concurrent snapshot fan-out shares one process-local connection
pool instead of racing to replace it. Focused regression coverage is in
`tests/test_supabase_read_efficiency.py`; these changes preserve response
shapes and authorization behavior.

## Regression Guard Tests

- `tests/test_performance_hotpaths.py`
- `tests/test_supabase_read_efficiency.py`
- `tests/test_deadline_utils.py`
- `tests/test_startup_bootstrap.py`

Run locally:

```bash
python -m pytest -q tests/test_performance_hotpaths.py
```

## Check-In Snapshot RPC (Supabase API Mode)

The consolidated `ritual.snapshot` read kind (`fn_ritual_snapshot` RPC, migration `y2d3e4f5a6b7`) replaces the per-section fan-out for the Check-In page in Supabase API mode:

- Warm RPC round trip: ~0.65-0.72 s (vs ~1.9 s for the legacy concurrent fan-out over the free-tier pooler).
- Single SQL execution returns key results, weekly plan, retrospectives, work logs, and experiments.
- Fallback to the legacy fan-out occurs only on missing-function errors (SQLSTATE 42883); all other failures propagate fail-closed.


## Supabase read fan-out optimization (2026-09-02)

Code inspection of the instrumented read path identified `tasks.by_cycle` as the highest-round-trip hierarchy read: the legacy path performs sequential `goal`, `objective`, `key_result`, and `task` requests. It now prefers a single nested PostgREST `task` query using the existing foreign-key relationships and strips the embedded filter carrier before returning the established response shape.

Expected reduction: 4 remote round trips to 1 on current schemas, a 75% reduction in request count and removal of three sequential network waits. A compatibility fallback preserves the previous four-request path when the Supabase project does not expose the relationships through PostgREST. Focused contract tests pass (`3 passed`).

## Backend read-query phase attribution (2026-09-02)

The remaining Supabase API-mode `app` time is now split into safe,
request-local `Server-Timing` phases for `POST /v1/read/query`:

- `actor`: header/payload actor binding performed by the route.
- `scope`: authorization scope resolution and validation before any read is dispatched.
- `handler`: the selected read handler, including its Supabase transport calls and local response shaping.
- `data`: the accumulated HTTP time spent in Supabase transport calls.
- `app`: total backend request time excluding `data`; it remains the aggregate fallback metric.

The phase values are durations only; no payloads, SQL, credentials, or actor
identifiers are emitted. `handler` is intentionally inclusive of `data`, so
the useful residual is `handler - data`. The remaining request residual after
the phase timers is response-model validation/serialization and framework
overhead. This instrumentation is contract-preserving and has focused
coverage in `tests/test_backend_observability.py`.

No further optimization is justified from the prior aggregate measurement
alone. The next live Supabase probe should capture these phase values and
decide between:

1. `scope` dominant: reduce or cache scope resolution only with an explicit
   authorization invalidation contract.
2. `handler - data` dominant: profile local mapping/response shaping before
   changing query behavior.
3. Residual dominant: profile FastAPI response validation/serialization and
   payload size.
### Weekly-plan mutation SLO correction - 2026-09-02

The disposable workload initially reported `10/10` weekly-plan errors because
the probe retained the CSRF header but omitted the matching
`okr_csrf_token` cookie. The BFF correctly rejected those requests with
`INVALID_CSRF_TOKEN`; authorization was not weakened.

The probe now sends both session and CSRF cookies, and preserves the
authenticated `user_id` when no active cycle exists. The weekly-plan route
does not require a cycle, so this avoids generating the invalid `user_id=0`
fixture payload while leaving cycle-dependent probes unchanged.

Final disposable workload evidence after the fix:

- Weekly-plan mutation: `0/10` errors, PASS (`201 Created` round trips).
- Read/query: `1.329s` p95, PASS.
- Login: `1.624s` p95, PASS.
- Snapshot: `0/6`, unavailable because the disposable workload had no active
  cycle; this is a missing cycle fixture prerequisite, not a weekly-plan
  mutation failure.
- Queue: `503`, explicitly unchanged and unsupported in Supabase API mode.

The synthetic weekly-plan row and disposable `slo-probe` account were deleted
after the run.

The probe contract was subsequently hardened so a repeat run can satisfy the
snapshot prerequisite without modifying existing provider data: use the paired
`--prepare-snapshot-fixture --confirm-disposable` opt-in described above. The
default probe remains strictly read-only with respect to cycle data.
