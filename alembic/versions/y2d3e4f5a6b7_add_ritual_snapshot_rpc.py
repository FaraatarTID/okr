"""Add fn_ritual_snapshot RPC for consolidated Check-In snapshot reads.

Creates a security-invoker Postgres function that returns the full Check-In
workspace snapshot (KRs needing check-in, weekly plan, retros, work logs,
experiments) in one round trip, replacing the multi-request REST fan-out.

Authorization contract (see docs/PLAN_CHECKIN_SNAPSHOT_RPC.md §3):
- Single identity input: p_username. The actor's numeric id is resolved
  inside the function; no caller-supplied user/owner ids are trusted.
- Role visibility: admin = all active users; manager = self + active direct
  reports; member = self only. Mirrors _resolve_actor_scope exactly.
- EXECUTE granted only to the configured runtime role (RUNTIME_DB_ROLE env var,
  default service_role). Revoked from public/anon/authenticated.
- Index policy: check_in(key_result_id, created_at desc) is created only if
  missing; removal decision is recorded here rather than auto-dropped.

Revision ID: y2d3e4f5a6b7
Revises: x1f2e3d4c5b6a
Create Date: 2026-08-24 00:00:00.000000
"""

import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text as sa_text

# revision identifiers, used by Alembic.
revision: str = "y2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "x1f2e3d4c5b6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FUNCTION_SIGNATURE = (
    "public.fn_ritual_snapshot(text, integer, timestamptz, timestamptz, timestamptz)"
)

_FN_BODY = """
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
set search_path = pg_catalog, public
as $fn$
declare
    v_actor_id integer;
    v_role text;
    v_is_admin boolean;
    v_owner_ids integer[];
begin
    -- §3.1: resolve the single authoritative actor identity.
    -- u.role is a Postgres enum (userrole); cast to text explicitly because
    -- trim()/lower() have no enum overloads (btrim(userrole) does not exist).
    select u.id, lower(trim(u.role::text)) into v_actor_id, v_role
    from public."user" as u
    where u.username = p_username and u.is_active
    limit 1;

    if v_actor_id is null then
        raise insufficient_privilege;
    end if;
    v_is_admin := (v_role = 'admin');

    -- §3.2: owner-id set per role (mirrors _resolve_actor_scope).
    if v_is_admin then
        select coalesce(array_agg(u.id), array[v_actor_id]) into v_owner_ids
        from public."user" as u
        where u.is_active;
    elsif v_role = 'manager' then
        select coalesce(array_agg(distinct uid), array[v_actor_id]) into v_owner_ids
        from (
            select u.id as uid from public."user" as u
            where u.is_active and (u.id = v_actor_id or u.manager_id = v_actor_id)
            union
            select v_actor_id
        ) as members;
    else
        v_owner_ids := array[v_actor_id];
    end if;

    -- §4.2: five sections computed set-based from v_actor_id / v_owner_ids.
    return jsonb_build_object(
        'key_results', (
            select coalesce(jsonb_agg(to_jsonb(kr) - 'goal_id' - 'objective_id' || jsonb_build_object('__tablename__', 'keyresult')), '[]'::jsonb)
            from (
                select kr.*
                from public.key_result as kr
                join public.objective as o on o.id = kr.objective_id
                join public.goal as g on g.id = o.goal_id
                join public.check_in as ci on ci.key_result_id = kr.id
                where g.cycle_id = p_cycle_id
                  and g.owner_id = any (v_owner_ids)
                group by kr.id
                having max(ci.created_at) < p_stale_before
                union all
                select kr.*
                from public.key_result as kr
                join public.objective as o on o.id = kr.objective_id
                join public.goal as g on g.id = o.goal_id
                where g.cycle_id = p_cycle_id
                  and g.owner_id = any (v_owner_ids)
                  and not exists (
                      select 1 from public.check_in as ci
                      where ci.key_result_id = kr.id
                  )
            ) as kr
        ),
        'weekly_plan', (
            select to_jsonb(wp)
            from public.weekly_plan as wp
            where wp.user_id = v_actor_id and wp.is_active
            order by wp.created_at desc
            limit 1
        ),
        'retros', (
            select coalesce(jsonb_agg(to_jsonb(r)), '[]'::jsonb)
            from public.retrospective as r
            where r.user_id = v_actor_id and r.cycle_id = p_cycle_id
        ),
        'work_logs', (
            select coalesce(jsonb_agg(jsonb_build_object(
                'id', wl.id, 'task_id', wl.task_id,
                'start_time', wl.start_time, 'end_time', wl.end_time,
                'duration_minutes', wl.duration_minutes,
                'summary', wl.summary, 'note', wl.note
            ) order by wl.start_time desc), '[]'::jsonb)
            from public.work_log as wl
            join public.task as t on t.id = wl.task_id
            where t.assignee_id = v_actor_id
              and wl.start_time >= p_window_start
              and wl.start_time <= p_window_end
        ),
        'experiments', (
            select coalesce(jsonb_agg(to_jsonb(e)), '[]'::jsonb)
            from public.experiment as e
            where e.cycle_id = p_cycle_id
              and (
                (e.end_at >= p_window_start and e.end_at < p_window_end)
                or e.status = 'RUNNING'
              )
        )
    );
end;
$fn$;
"""


def upgrade() -> None:
    # This migration is PostgreSQL-only: the RPC function uses plpgsql,
    # jsonb, and Postgres grants. SQLite (used by local tests/dev) skips it.
    bind = op.get_bind()
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "")).lower()
    if dialect_name != "postgresql":
        print(
            f"Skipping fn_ritual_snapshot creation on non-postgresql dialect "
            f"({dialect_name or 'unknown'})."
        )
        return

    # Create the function first (idempotent).
    op.execute(_FN_BODY)

    # Grants: revoke broad access, grant only to the configured runtime role.
    # Supabase-specific roles (anon, authenticated) do not exist on plain
    # Postgres (e.g. compose smoke / self-hosted), so each role is checked for
    # existence before revoking/granting instead of failing the migration.
    runtime_role = os.environ.get("RUNTIME_DB_ROLE", "service_role").strip()
    if not runtime_role:
        runtime_role = "service_role"

    def _role_exists(role_name: str) -> bool:
        return bool(
            bind.execute(
                sa_text("select 1 from pg_roles where rolname = :role"),
                {"role": role_name},
            ).scalar()
        )

    for revoke_role in ("public", "anon", "authenticated"):
        if revoke_role == "public" or _role_exists(revoke_role):
            op.execute(
                f"revoke execute on function {_FUNCTION_SIGNATURE} "
                f"from {revoke_role}"
            )
        else:
            print(f"Role '{revoke_role}' not found; skipping revoke.")

    if _role_exists(runtime_role):
        op.execute(f"grant execute on function {_FUNCTION_SIGNATURE} to {runtime_role}")
    else:
        print(
            f"Runtime DB role '{runtime_role}' not found; skipping EXECUTE grant "
            "(function remains revoked from public)."
        )

    # Supporting index for the latest-check-in lateral lookup. Created only if
    # missing; retained on downgrade (benefits other queries too).
    op.execute(
        "create index if not exists ix_check_in_kr_created "
        "on public.check_in (key_result_id, created_at desc)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "")).lower()
    if dialect_name != "postgresql":
        print(
            f"Skipping fn_ritual_snapshot drop on non-postgresql dialect "
            f"({dialect_name or 'unknown'})."
        )
        return
    op.execute(f"drop function if exists {_FUNCTION_SIGNATURE}")
