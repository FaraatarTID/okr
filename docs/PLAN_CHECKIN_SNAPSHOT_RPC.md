Documentation HQ: [README](../README.md)

# Production Implementation Plan: Server-Side Check-In Snapshot (RPC)

Status: **Revised plan (v2.1) — approved with pre-implementation amendments applied.**
Owner: backend architecture.
Related: `docs/ALPHA_TEST_PROFILES.md`, `backend_app/read_query_helpers.py` (`ritual.snapshot`), `src/services/supabase_api_mode_read.py`, `backend_app/scope_resolution.py`.

## Revision history

- **v2.1**: Applied final review amendments: explicit `RUNTIME_DB_ROLE`
  configuration replaces dynamic `current_user` role inference; effective-
  privilege testing including role inheritance; fully qualified relation
  names and tightened search_path wording; N+1 execution criterion replaces
  the over-prescriptive nested-loop prohibition; representative benchmark
  dataset defined behind the 250 ms threshold; adversarial `p_cycle_id`
  authorization tests added (§6.1 cases 11–14); function reclassified as a
  privileged read projection with an explicit authorization contract.
- **v2**: Addressed external security review. Single identity input (removed
  independent `p_user_id`); explicit admin predicate derived from
  `UserRole` normalization; grants restricted to the backend runtime role;
  adversarial cross-identity test matrix; only SQLSTATE `42883` triggers
  fallback; explicit time-window parameters (no DB-side `now()` defaults);
  EXPLAIN-based performance acceptance; three-way equivalence testing.
- v1: Initial draft.

## 1. Problem

The Check-In workspace currently loads five datasets. The first optimization
(`ritual.snapshot`) collapsed five browser/BFF requests into one, and bounded
Supabase-mode upstream reads run concurrently (five workers). However, in
Supabase API mode the snapshot still issues many sequential REST calls:

- `krs.needing_checkin`: goals -> objectives -> key_results -> one check_in
  query **per KR** (N+1 pattern)
- `weekly_plan.active`
- `retros.user`
- `work_logs.by_range`: tasks -> work_log
- `experiments.for_retro_window`

At ~1s per REST round trip this is the dominant remaining latency, and it grows
with KR count.

## 2. Goal

Replace the Supabase-mode fan-out with a single authorized Postgres function
(RPC) that returns the entire Check-In snapshot in one round trip, while
preserving identical authorization semantics and response shape.

Non-goals:

- Changing the browser/BFF contract (`ritual.snapshot` request/response stays).
- Replacing direct-Postgres mode behavior (already a single-session path).
- Introducing new dependencies.

## 3. Security model (normative)

This section is the authoritative security specification. Implementation must
match it exactly.

### 3.0 Threat model and trust boundaries

```text
Browser (untrusted)
   |  session cookie (BFF-validated)
spa-bff (session + CSRF + allowlist + actor rewrite)
   |  service token + HMAC signature + x-okr-actor
backend-api (service-token gate; scope gate before dispatch)
   |  service-role key (bypasses Supabase RLS)
Supabase Postgres (fn_ritual_snapshot SQL predicates = final enforcement)
```

**Normative statement:** because the transport authenticates with the
service-role key, Supabase RLS is bypassed for these calls. The SQL predicates
inside `fn_ritual_snapshot` are therefore the final authorization boundary for
the data it returns. The function must be written as if its arguments are
hostile.

### 3.1 Single identity input

The function accepts **only** `p_username text` as the actor identity. There is
no `p_user_id` parameter. The actor's numeric ID is resolved inside the
function:

```sql
select id, lower(trim(role)) into v_actor_id, v_role
from "user"
where username = p_username and is_active
limit 1;

if v_actor_id is null then
    raise insufficient_privilege;  -- unknown/inactive actor -> 403 upstream
end if;
```

Every section derives its user scoping from `v_actor_id`. The invariant is:

> One request -> one authoritative actor identity (`p_username`) ->
> one resolved `v_actor_id` -> every subsection filters on `v_actor_id`
> (or the admin-expanded owner set).

The backend caller passes `actor_username` (the authenticated session actor),
never a client-supplied user id. The existing scope gate
(`_validate_supabase_read_scope`) additionally enforces
`_require_allowed_username(scope, p_username)` before dispatch.

### 3.2 Role and admin predicate (exact specification)

Roles are stored lowercase per `UserRole` (`admin`, `manager`, `member`;
see `src/models.py`). The function must reproduce this normalization:

```sql
v_role := lower(trim(resolved.role));
v_is_admin := (v_role = 'admin');
```

Visibility rules (must match `_resolve_actor_scope` in
`backend_app/scope_resolution.py` exactly):

| Role | owner_ids set |
| --- | --- |
| admin | all active users |
| manager | self + active users whose `manager_id = actor id` |
| member | self only |

Tests must cover all three roles explicitly (see §6).

### 3.3 Grants

The migration grants EXECUTE **only** to the explicitly configured backend
runtime database role — the role used by the application/Supabase API transport
connection string. It MUST NOT grant to `anon`, `authenticated`, or `public`.
The runtime role MUST come from explicit configuration (`RUNTIME_DB_ROLE`
environment variable consumed by the migration via Alembic's env.py, defaulting
to `service_role` on Supabase-hosted runtimes). The migration MUST NOT infer
the runtime role from its own execution identity (`current_user`): migration
execution (often a migration/admin role) and application runtime are separate
concerns.

```sql
revoke execute on function
    public.fn_ritual_snapshot(text, integer, timestamptz, timestamptz, timestamptz)
from public, anon, authenticated;
grant execute on function
    public.fn_ritual_snapshot(text, integer, timestamptz, timestamptz, timestamptz)
to :runtime_db_role;  -- bound from RUNTIME_DB_ROLE at migration time
```

Effective privilege must be verified by test, not by ACL inspection alone:
PostgreSQL roles can inherit privileges through membership, so the test suite
executes the function as (a) the runtime role (must succeed), (b) `anon`/
unauthenticated (must fail), (c) `authenticated` (must fail), and (d) an
ordinary non-runtime application role (must fail). If `service_role` is the
configured runtime role, that exact role is tested.

## 4. Design

### 4.1 Function signature (no defaults; fully explicit)

```sql
create or replace function public.fn_ritual_snapshot(
    p_username text,
    p_cycle_id integer,
    p_stale_before timestamptz,
    p_window_start timestamptz,
    p_window_end timestamptz
)
returns jsonb
language plpgsql
security invoker
stable
set search_path = public
as $$
declare
    v_actor_id integer;
    v_role text;
    v_is_admin boolean;
begin
    -- §3.1: resolve the single authoritative actor identity.
    select id, lower(trim(role)) into v_actor_id, v_role
    from "user"
    where username = p_username and is_active
    limit 1;

    if v_actor_id is null then
        raise insufficient_privilege;
    end if;
    v_is_admin := (v_role = 'admin');

    -- §4.2 CTEs compute all five sections using v_actor_id / v_is_admin only.
    ...
end;
$$;
```

Notes:

- No `now()` defaults anywhere. The backend computes `p_window_start`,
  `p_window_end`, and derives the check-in staleness cutoff from
  `p_days_threshold` **in Python**, passing it as the explicit parameter
  `p_stale_before timestamptz`, so time semantics are identical between the
  legacy path and the RPC.
- `stable` is valid: no writes; no DB-side clock reads inside the function.
- All relation references inside the function body are schema-qualified
  (`public."user"`, `public.goal`, etc.). `set search_path = pg_catalog, public`
  is set as defense-in-depth, but the security argument does not depend on
  search_path behavior: qualified names make the function immune to
  search-path hijacking of unqualified references.

### 4.2 Section semantics (must match legacy exactly)

Derived context: `v_actor_id`, `v_is_admin`, and the owner-id set computed once
per §3.2 rules.

1. **key_results** — KRs in cycle where goal owner ∈ owner_ids, KR state =
   `'active'`, and (no check-in OR latest check-in created_at < p_stale_before).
   Latest check-in via lateral join on `(key_result_id, created_at desc)`
   limit 1.
2. **weekly_plan** — single row: `user_id = v_actor_id and is_active`,
   latest by `created_at desc`.
3. **retros** — `user_id = v_actor_id and cycle_id = p_cycle_id`.
4. **work_logs** — work_logs joined to tasks where task assignee =
   `v_actor_id` and start_time within `[p_window_start, p_window_end]`.
5. **experiments** — `cycle_id = p_cycle_id` and
   `(end_at in window or status = 'RUNNING')`.

All sections serialize via `jsonb_build_object` with keys matching the current
contract exactly.

### 4.3 Backend integration

In `read_query_via_supabase_api` (supabase_api_mode_read.py):

- New `_rest_rpc` helper: `POST /rest/v1/rpc/fn_ritual_snapshot`.
- Kind `ritual.snapshot` dispatches to it with explicit parameters; response
  wrapped internally as `{"snapshot": <object>}`.

In `read_query_helpers.py` (`ritual.snapshot` branch):

- Scope gate runs first (unchanged).
- Supabase mode calls the RPC path instead of the five sub-queries.
- Direct-Postgres mode keeps current handlers (single session, efficient).

### 4.4 Fallback: only SQLSTATE 42883

Only `42883` (undefined_function) triggers the concurrent fan-out fallback,
latched for process lifetime with a single warning log. All other failures
propagate:

| SQLSTATE | Meaning | Behavior |
| --- | --- | --- |
| `42883` | Function missing | Fallback (compatibility) |
| `42501` | Insufficient privilege | **Propagate as failure** |
| `57014` | Query canceled | **Propagate as failure** |
| `P0001`+ | Function-raised errors | **Propagate as failure** |

Network/transport failures raise `SupabaseTransportError` (existing typed
error) and also propagate. The fallback must never mask authorization or
data errors.

## 5. Migration

New Alembic revision (head after `x1f2e3d4c5b6a`), following the defensive
inspector conventions of `u1c2d3e4f5a6_add_user_token_version.py`:

- `upgrade()`:
  - `create or replace function fn_ritual_snapshot(...)` (signature above).
  - Revoke EXECUTE from `public`, `anon`, `authenticated`; grant EXECUTE to
    the runtime role (explicit, environment-aware — see §3.3).
  - Index policy: do **not** blindly add `check_in(key_result_id, created_at)`.
    The migration includes a verification step: run
    `explain (analyze, buffers)` for the latest-check-in lateral query against
    representative data in staging; add the index only if the plan shows a
    sequential scan on `check_in`. Record the decision in the migration docstring.
- `downgrade()`: drop the function. Do not drop any index added conditionally
  without the same inspection guard.

Note on future changes: PostgreSQL treats a changed signature as a new
function. Any future signature change requires a new migration that drops the
old signature explicitly.

## 6. Testing

### 6.1 Authorization matrix (adversarial — mandatory)

Fixture: users Alice (member), Bob (member), Carol (manager of Bob), Dave
(admin); goals/KRs owned variously; cycles A and B.

| # | Actor | Requested context | Expected |
| --- | --- | --- | --- |
| 1 | Alice (member) | own goals, cycle A | only Alice-owned KRs |
| 2 | Bob (member) | own goals, cycle A | only Bob-owned KRs |
| 3 | Carol (manager) | self + Bob's KRs | Carol + Bob KRs, not Alice's |
| 4 | Dave (admin) | cycle A | all KRs in cycle A |
| 5 | Alice | **cross-identity probe** (legacy caller passes user_id = Bob) | only Alice-owned data; nothing of Bob's |
| 6 | Unknown username | any | insufficient_privilege error |
| 7 | Inactive user | any | insufficient_privilege error |
| 8 | Alice | empty cycle | empty sections, no error |
| 9 | Alice | NULL-valued fields present | nulls serialized correctly |
| 10 | Boundary timestamps | check-in exactly at stale boundary | deterministic inclusion/exclusion per spec |
| 11 | Alice | cycle B containing only Bob-owned data | no Bob data returned |
| 12 | Carol (manager) | cycle B | only Carol + direct-report data |
| 13 | Dave (admin) | arbitrary valid cycle | all permitted cycle data |
| 14 | Any actor | invalid/nonexistent cycle id | empty sections; exact legacy behavior for that case |

Cases 11–14 close the `p_cycle_id` boundary: changing `p_cycle_id` must never
expand actor visibility beyond the legacy authorization model. Case 14 pins
the nonexistent-cycle behavior to whatever the legacy fan-out does today
(empty sections vs error), so the RPC cannot diverge.

Case 5 is the confused-deputy probe: since the function has no `p_user_id`,
the test proves no cross-user leakage is possible through any argument. For the
legacy fan-out path, case 5 additionally verifies that
`_validate_supabase_read_scope` rejects a `user_id` outside the caller's scope.

### 6.2 Semantic equivalence (three-way)

For identical fixtures, assert deep equality of JSON output across:

1. Legacy Supabase fan-out (current implementation)
2. `fn_ritual_snapshot` RPC
3. Direct-Postgres recursive handlers

Run over the full §6.1 matrix plus threshold/window semantics tests
(recent check-in excluded; stale included; none included; experiments inside/
outside window; RUNNING always included).

### 6.3 Performance acceptance

Representative benchmark dataset (defined; used for all thresholds):

| Dimension | Value |
| --- | --- |
| Users | 50 (5 admins, 10 managers, 35 members) |
| Goals | 200 (distributed across cycles) |
| Objectives | 600 |
| Key Results | 1,800 (>= 1,000 in the measured cycle) |
| Check-ins | >= 10,000 (mixed fresh/stale relative to threshold) |
| Tasks | 3,000 |
| Work logs | 12,000 |
| Retros / experiments / weekly plans | 300 / 400 / 150 |
| Distribution | KRs spread across members and managers; manager and admin cases included |
| Environment | Staging Postgres (Supabase), warm cache, documented PostgreSQL version |

Acceptance criteria:

- `explain (analyze, buffers)` captured for the function body's main queries on
  the benchmark dataset.
- Execution demonstrates **set-based behavior with no N+1 query execution**:
  no per-KR or per-row query issuance. Indexed parameterized lookups are
  acceptable where the planner demonstrates bounded cost; a sequential scan on
  `check_in` is acceptable only at small table sizes where the planner proves
  it cheaper than index access — at benchmark volume the latest-check-in
  operation must use an index-supported access path.
- DB execution time measured separately from HTTP latency; regression
  threshold: warm DB execution < 250 ms on the benchmark dataset.
- One HTTP round trip per snapshot load in Supabase API mode.

### 6.4 Regression

- Full `pytest -k "supabase_api or read_query or scope"` green.
- `useAtlasModeData` tests unchanged and green (frontend contract intact).

## 7. Rollout

1. Merge migration + code behind the fallback design (safe either order).
2. Deploy backend images (api + worker).
3. Run `alembic upgrade head` against Supabase.
4. Verify via container smoke test and the UI Check-In flow.
5. Watch logs for fallback warnings ("RPC missing") over one cycle.

Rollback: revert code (fallback engages automatically); optionally drop the
function via downgrade. No data migration risk.

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| SQL drift between function and ORM predicates | Three-way golden equivalence tests (§6.2) |
| Cross-user leakage via arguments | Single identity input; adversarial matrix §6.1 case 5 |
| Over-broad EXECUTE grants | Explicit revoke from public/anon/authenticated; grant to runtime role only (§3.3) |
| Fallback masking real failures | Only SQLSTATE 42883 falls back; all else propagates (§4.4) |
| Time-semantics drift between Python and SQL | Backend computes all timestamps; no DB-side now() defaults (§4.1) |
| Expensive function hiding behind "one RTT" | EXPLAIN-based acceptance + regression threshold (§6.3) |
| Future signature change creates duplicate function | Migration note: signature changes require explicit drop (§5) |

## 9. Acceptance criteria

- One Supabase round trip per Check-In snapshot load in API mode.
- Response shape identical to today (frontend untouched).
- Authorization equivalent to the app-layer predicates, proven by the §6.1
  adversarial matrix including the cross-identity probe.
- Fallback triggered exclusively by SQLSTATE 42883; all other errors propagate.
- EXPLAIN evidence of set-based execution with bounded DB time (< 250 ms warm
  at representative volume).
- All existing tests green plus new RPC tests.
