"""Read-only Supabase HTTPS API helper functions for snapshot, metrics, and queries."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from src.services.supabase_api_mode_transport import (
    _as_int,
    _cycle_select_fields,
    _decorate_node_row,
    _normalize_user_row_role,
    _in_clause_ids,
    _parse_dt,
    _rest_select,
)
from src.services.supabase_api_mode_transport import (
    SupabaseTransportError,
    _request_json_with_method,
)


def _rest_rpc(function_name: str, args: dict[str, Any]) -> tuple[int, Any]:
    """Call a Postgres function via PostgREST RPC.

    Returns (status, payload) like other transport helpers. Raises
    SupabaseTransportError on network/timeout failures; HTTP errors are
    surfaced as status codes for the caller to interpret.
    """
    return _request_json_with_method(
        "POST",
        f"/rest/v1/rpc/{function_name}",
        body=args,
    )


def read_query_via_supabase_api(
    *, kind: str, params: dict[str, Any], actor: str
) -> dict[str, Any]:
    normalized = str(kind or "").strip()

    if normalized == "ritual.snapshot":
        days_threshold = int(params.get("days_threshold") or 7)
        stale_before = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        window_start = str(params.get("window_start") or "").strip()
        window_end = str(params.get("window_end") or "").strip()
        if not window_start or not window_end:
            raise ValueError("window_start and window_end are required.")
        username = str(params.get("actor_username") or actor or "").strip()
        cycle_id = int(params.get("cycle_id") or 0)
        if not username or cycle_id <= 0:
            raise ValueError("actor_username and cycle_id are required.")
        try:
            status, snapshot = _rest_rpc(
                "fn_ritual_snapshot",
                {
                    "p_username": username,
                    "p_cycle_id": cycle_id,
                    "p_stale_before": stale_before.isoformat(),
                    "p_window_start": window_start,
                    "p_window_end": window_end,
                },
            )
        except SupabaseTransportError:
            # Network-level failures propagate as typed errors; only the
            # missing-function case (42883) is handled by the caller's
            # fallback logic in read_query_helpers.py.
            raise
        if status < 400 and isinstance(snapshot, dict):
            return {"snapshot": snapshot}
        # HTTP error: distinguish missing function (42883/PGRST202) from other
        # failures so read_query_helpers can fall back only for 42883.
        detail = ""
        if isinstance(snapshot, dict):
            detail = str(snapshot.get("message") or snapshot.get("error") or "")
        code = ""
        if isinstance(snapshot, dict):
            code = str(snapshot.get("code") or "")
        if status == 404 and (code in {"42883", "PGRST202"} or "does not exist" in detail):
            exc = ValueError(
                f"Supabase API error (ritual.snapshot): function missing "
                f"(SQLSTATE 42883): {detail}"
            )
            raise exc
        raise ValueError(
            f"Supabase API error (ritual.snapshot): HTTP {status}: {detail}"
        )

    _ = actor
    normalized = str(kind or "").strip()

    if normalized == "audit.summary":
        safe_days = max(1, int(params.get("days") or 30))
        safe_recent_limit = max(1, min(100, int(params.get("recent_limit") or 20)))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=safe_days)).isoformat()
        query: dict[str, str] = {
            "select": "id,actor,actor_user_id,actor_role,actor_team_id,action,entity,result,target_type,target_id,target_owner_id,target_team_id,correlation_id,request_id,created_at",
            "created_at": f"gte.{cutoff}",
            "order": "created_at.desc,id.desc",
            "limit": "500",
        }
        for key in (
            "action",
            "entity",
            "actor",
            "actor_role",
            "target_type",
            "correlation_id",
            "request_id",
            "result",
        ):
            value = params.get(key)
            if value is not None and str(value).strip():
                query[key] = f"eq.{str(value).strip()}"
        for key in (
            "actor_user_id",
            "actor_team_id",
            "target_id",
            "target_owner_id",
            "target_team_id",
        ):
            value = params.get(key)
            if value is not None and str(value).strip():
                query[key] = f"eq.{_as_int(value, 0)}"

        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page_query = dict(query)
            page_query["offset"] = str(offset)
            status, page_rows = _rest_select("audit_event", query=page_query)
            if status >= 400:
                raise ValueError(f"Supabase API error (audit.summary): {status}")
            rows.extend(page_rows)
            if len(page_rows) < 500:
                break
            offset += 500

        if not rows:
            return {
                "window_days": safe_days,
                "recent_limit": safe_recent_limit,
                "total_events": 0,
                "success_events": 0,
                "failure_events": 0,
                "latest_event_at": None,
                "by_actor_role": [],
                "by_actor_team_id": [],
                "by_target_type": [],
                "by_entity": [],
                "by_action": [],
                "recent_events": [],
            }

        def _count_by(field: str) -> list[dict[str, Any]]:
            counter: Counter[Any] = Counter()
            for row in rows:
                value = row.get(field)
                if value is None:
                    continue
                counter[value] += 1
            items = [
                {"value": value, "count": int(count)}
                for value, count in counter.items()
            ]
            items.sort(key=lambda item: (-int(item["count"]), str(item["value"])))
            return items

        success_events = sum(
            1 for row in rows if str(row.get("result") or "").lower() == "success"
        )
        failure_events = sum(
            1 for row in rows if str(row.get("result") or "").lower() == "failure"
        )

        return {
            "window_days": safe_days,
            "recent_limit": safe_recent_limit,
            "total_events": len(rows),
            "success_events": success_events,
            "failure_events": failure_events,
            "latest_event_at": rows[0].get("created_at"),
            "by_actor_role": _count_by("actor_role"),
            "by_actor_team_id": _count_by("actor_team_id"),
            "by_target_type": _count_by("target_type"),
            "by_entity": _count_by("entity"),
            "by_action": _count_by("action"),
            "recent_events": rows[:safe_recent_limit],
        }

    if normalized == "users.by_username":
        username = str(params.get("username") or "").strip()
        if not username:
            return {"user": None}
        status, rows = _rest_select(
            "user",
            query={
                "username": f"eq.{username}",
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.by_username): {status}")
        return {"user": _normalize_user_row_role(rows[0]) if rows else None}

    if normalized == "users.by_id":
        user_id = int(params.get("user_id") or 0)
        status, rows = _rest_select(
            "user",
            query={
                "id": f"eq.{user_id}",
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.by_id): {status}")
        return {"user": _normalize_user_row_role(rows[0]) if rows else None}

    if normalized == "users.all":
        status, rows = _rest_select(
            "user",
            query={
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.all): {status}")
        return {"users": [_normalize_user_row_role(row) for row in rows]}

    if normalized == "users.team_members":
        manager_id = int(params.get("manager_id") or 0)
        status, rows = _rest_select(
            "user",
            query={
                "manager_id": f"eq.{manager_id}",
                "select": "id,username,display_name,role,manager_id,team_id,is_active,must_change_password",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (users.team_members): {status}")
        return {"users": [_normalize_user_row_role(row) for row in rows]}

    if normalized == "teams.all":
        status, rows = _rest_select(
            "team",
            query={
                "select": "id,name,description,created_at",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (teams.all): {status}")
        return {"teams": rows}

    if normalized == "teams.by_id":
        team_id = int(params.get("team_id") or 0)
        status, rows = _rest_select(
            "team",
            query={
                "id": f"eq.{team_id}",
                "select": "id,name,description,created_at",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (teams.by_id): {status}")
        return {"team": rows[0] if rows else None}

    if normalized == "cycles.all":
        status, rows = _rest_select(
            "cycle",
            query={
                "select": _cycle_select_fields(),
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (cycles.all): {status}")
        return {"cycles": rows}

    if normalized == "cycles.active":
        status, rows = _rest_select(
            "cycle",
            query={
                "is_active": "eq.true",
                "select": _cycle_select_fields(),
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (cycles.active): {status}")
        return {"cycles": rows}

    if normalized == "node.detect_type":
        node_id = int(params.get("node_id") or 0)
        for table, node_type in (
            ("goal", "GOAL"),
            ("objective", "OBJECTIVE"),
            ("key_result", "KEY_RESULT"),
            ("task", "TASK"),
        ):
            status, rows = _rest_select(
                table,
                query={"id": f"eq.{node_id}", "select": "id", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (node.detect_type/{table}): {status}"
                )
            if rows:
                return {"node_type": node_type}
        return {"node_type": None}

    if normalized == "node.get":
        node_id = _as_int(params.get("node_id"), 0)
        requested_node_type = str(params.get("node_type") or "").strip().upper()
        table_by_type = {
            "GOAL": "goal",
            "OBJECTIVE": "objective",
            "KEY_RESULT": "key_result",
            "TASK": "task",
        }
        requested_table = table_by_type.get(requested_node_type)
        if requested_table is None:
            return {"node": None}
        status, rows = _rest_select(
            requested_table, query={"id": f"eq.{node_id}", "select": "*", "limit": "1"}
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (node.get/{requested_table}): {status}"
            )
        if not rows:
            return {"node": None}
        return {"node": _decorate_node_row(rows[0], table=requested_table)}

    if normalized == "krs.by_cycle":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        limit = params.get("limit")
        offset = _as_int(params.get("offset"), 0)

        # Prefer one embedded PostgREST query over walking the goal ->
        # objective -> key-result hierarchy with three sequential remote
        # calls. Keep the existing path as a compatibility fallback for
        # projects whose PostgREST schema cache lacks the relationship.
        nested_query: dict[str, str] = {
            "select": "*,objective!inner(goal_id)",
            "objective.goal_id": f"eq.{cycle_id}",
            "order": "id.asc",
        }
        if limit is not None:
            nested_query["limit"] = str(_as_int(limit, 0))
        if offset > 0:
            nested_query["offset"] = str(offset)
        status, nested_krs = _rest_select("key_result", query=nested_query)
        if status < 400:
            for row in nested_krs:
                # The embedded relation is only a cycle filter; preserve the
                # established key-result response shape for callers.
                row.pop("objective", None)
                row["__tablename__"] = "keyresult"
            return {"key_results": nested_krs}

        q = {"cycle_id": f"eq.{cycle_id}", "select": "id", "order": "id.asc"}
        status, goals = _rest_select("goal", query=q)
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.by_cycle/goals): {status}")
        goal_ids = [
            str(_as_int(g.get("id"), 0)) for g in goals if _as_int(g.get("id"), 0) > 0
        ]
        if not goal_ids:
            return {"key_results": []}

        status, objectives = _rest_select(
            "objective",
            query={
                "goal_id": f"in.({_in_clause_ids(goal_ids)})",
                "select": "id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.by_cycle/objectives): {status}")
        objective_ids = [
            str(_as_int(o.get("id"), 0))
            for o in objectives
            if _as_int(o.get("id"), 0) > 0
        ]
        if not objective_ids:
            return {"key_results": []}

        kr_query = {
            "objective_id": f"in.({','.join(objective_ids)})",
            "select": "*",
            "order": "id.asc",
        }
        if limit is not None:
            kr_query["limit"] = str(_as_int(limit, 0))
        if offset > 0:
            kr_query["offset"] = str(offset)
        status, krs = _rest_select("key_result", query=kr_query)
        if status >= 400:
            raise ValueError(f"Supabase API error (krs.by_cycle/key_result): {status}")
        for row in krs:
            row["__tablename__"] = "keyresult"
        return {"key_results": krs}

    if normalized == "tasks.by_cycle":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        limit = params.get("limit")
        offset = _as_int(params.get("offset"), 0)

        # Prefer one embedded PostgREST query over walking the hierarchy with
        # four sequential remote calls. Older projects may not expose these
        # FK relationships through PostgREST, so retain the fallback below.
        nested_query: dict[str, str] = {
            "select": "*,key_result!inner(objective!inner(goal_id))",
            "key_result.objective.goal_id": f"eq.{cycle_id}",
            "order": "id.asc",
        }
        if limit is not None:
            nested_query["limit"] = str(_as_int(limit, 0))
        if offset > 0:
            nested_query["offset"] = str(offset)
        status, nested_tasks = _rest_select("task", query=nested_query)
        if status < 400:
            for row in nested_tasks:
                # The embedded relation is only a filter carrier; preserve
                # the established task response shape for callers.
                row.pop("key_result", None)
                row["__tablename__"] = "task"
            return {"tasks": nested_tasks}

        status, goals = _rest_select(
            "goal",
            query={"cycle_id": f"eq.{cycle_id}", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (tasks.by_cycle/goals): {status}")
        goal_ids = [
            str(_as_int(g.get("id"), 0)) for g in goals if _as_int(g.get("id"), 0) > 0
        ]
        if not goal_ids:
            return {"tasks": []}

        status, objectives = _rest_select(
            "objective",
            query={
                "goal_id": f"in.({_in_clause_ids(goal_ids)})",
                "select": "id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (tasks.by_cycle/objectives): {status}"
            )
        objective_ids = [
            str(_as_int(o.get("id"), 0))
            for o in objectives
            if _as_int(o.get("id"), 0) > 0
        ]
        if not objective_ids:
            return {"tasks": []}

        status, krs = _rest_select(
            "key_result",
            query={
                "objective_id": f"in.({','.join(objective_ids)})",
                "select": "id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (tasks.by_cycle/key_result): {status}"
            )
        kr_ids = [
            str(_as_int(k.get("id"), 0)) for k in krs if _as_int(k.get("id"), 0) > 0
        ]
        if not kr_ids:
            return {"tasks": []}

        task_query = {
            "key_result_id": f"in.({','.join(kr_ids)})",
            "select": "*",
            "order": "id.asc",
        }
        if limit is not None:
            task_query["limit"] = str(_as_int(limit, 0))
        if offset > 0:
            task_query["offset"] = str(offset)
        status, tasks = _rest_select("task", query=task_query)
        if status >= 400:
            raise ValueError(f"Supabase API error (tasks.by_cycle/task): {status}")
        for row in tasks:
            row["__tablename__"] = "task"
        return {"tasks": tasks}

    if normalized == "weekly_plan.active":
        user_id = _as_int(params.get("user_id"), 0)
        status, rows = _rest_select(
            "weekly_plan",
            query={
                "user_id": f"eq.{user_id}",
                "is_active": "eq.true",
                "select": "*",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (weekly_plan.active): {status}")
        return {"weekly_plan": rows[0] if rows else None}

    if normalized == "work_logs.by_task":
        task_id = _as_int(params.get("task_id"), 0)
        status, logs = _rest_select(
            "work_log",
            query={
                "task_id": f"eq.{task_id}",
                "select": "id,task_id,start_time,end_time,duration_minutes,summary,note",
                "order": "start_time.desc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (work_logs.by_task): {status}")
        return {"work_logs": logs}

    if normalized == "work_logs.by_range":
        user_id = _as_int(params.get("user_id"), 0)
        start_date = str(params.get("start_date") or "").strip()
        end_date = str(params.get("end_date") or "").strip()
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required.")

        status, tasks = _rest_select(
            "task",
            query={
                "assignee_id": f"eq.{user_id}",
                "select": "id,title,key_result_id,assignee_id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (work_logs.by_range/tasks): {status}")
        task_ids = [
            str(_as_int(t.get("id"), 0)) for t in tasks if _as_int(t.get("id"), 0) > 0
        ]
        if not task_ids:
            return {"work_logs": []}
        task_by_id = {_as_int(t.get("id"), 0): t for t in tasks}

        status, logs = _rest_select(
            "work_log",
            query={
                "task_id": f"in.({_in_clause_ids(task_ids)})",
                "and": f"(start_time.gte.{start_date},start_time.lte.{end_date})",
                "select": "id,task_id,start_time,end_time,duration_minutes,summary,note",
                "order": "start_time.desc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (work_logs.by_range/work_log): {status}"
            )
        for log in logs:
            tid = _as_int(log.get("task_id"), 0)
            task = task_by_id.get(tid)
            if task:
                log["task"] = {
                    "__tablename__": "task",
                    "id": _as_int(task.get("id"), 0),
                    "key_result_id": task.get("key_result_id"),
                    "title": task.get("title"),
                    "assignee_id": task.get("assignee_id"),
                }
        return {"work_logs": logs}

    if normalized == "krs.needing_checkin":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        days_threshold = _as_int(params.get("days_threshold"), 7)
        now_utc = datetime.now(timezone.utc)

        status, goals = _rest_select(
            "goal",
            query={"cycle_id": f"eq.{cycle_id}", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (krs.needing_checkin/goals): {status}"
            )
        goal_ids = [
            str(_as_int(g.get("id"), 0)) for g in goals if _as_int(g.get("id"), 0) > 0
        ]
        if not goal_ids:
            return {"key_results": []}

        status, objectives = _rest_select(
            "objective",
            query={
                "goal_id": f"in.({_in_clause_ids(goal_ids)})",
                "select": "id",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (krs.needing_checkin/objectives): {status}"
            )
        objective_ids = [
            str(_as_int(o.get("id"), 0))
            for o in objectives
            if _as_int(o.get("id"), 0) > 0
        ]
        if not objective_ids:
            return {"key_results": []}

        status, krs = _rest_select(
            "key_result",
            query={
                "objective_id": f"in.({_in_clause_ids(objective_ids)})",
                "select": "*",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (krs.needing_checkin/key_result): {status}"
            )

        selected: list[dict[str, Any]] = []
        kr_ids = [
            str(_as_int(kr.get("id"), 0))
            for kr in krs
            if _as_int(kr.get("id"), 0) > 0
        ]
        latest_checkin_by_kr: dict[int, datetime] = {}
        if kr_ids:
            c_status, checkins = _rest_select(
                "check_in",
                query={
                    "key_result_id": f"in.({_in_clause_ids(kr_ids)})",
                    "select": "key_result_id,created_at",
                    "order": "key_result_id.asc,created_at.desc",
                },
            )
            if c_status >= 400:
                raise ValueError(
                    f"Supabase API error (krs.needing_checkin/check_in): {c_status}"
                )
            for checkin in checkins:
                checkin_kr_id = _as_int(checkin.get("key_result_id"), 0)
                if checkin_kr_id <= 0 or checkin_kr_id in latest_checkin_by_kr:
                    continue
                latest = _parse_dt(checkin.get("created_at"))
                if latest is not None:
                    latest_checkin_by_kr[checkin_kr_id] = latest

        for kr in krs:
            kr_id = _as_int(kr.get("id"), 0)
            if kr_id <= 0:
                continue
            latest = latest_checkin_by_kr.get(kr_id)
            if latest is None:
                kr["__tablename__"] = "keyresult"
                selected.append(kr)
                continue
            age_days = (now_utc - latest).total_seconds() / 86400.0
            if age_days >= float(days_threshold):
                kr["__tablename__"] = "keyresult"
                selected.append(kr)
        return {"key_results": selected}

    if normalized == "experiments.active_for_kr":
        key_result_id = _as_int(params.get("key_result_id"), 0)
        status, rows = _rest_select(
            "experiment",
            query={
                "key_result_id": f"eq.{key_result_id}",
                "status": "eq.RUNNING",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (experiments.active_for_kr): {status}"
            )
        return {"experiments": rows}

    if normalized == "experiments.for_kr":
        key_result_id = _as_int(params.get("key_result_id"), 0)
        status, rows = _rest_select(
            "experiment",
            query={
                "key_result_id": f"eq.{key_result_id}",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (experiments.for_kr): {status}")
        return {"experiments": rows}

    if normalized == "experiments.for_retro_window":
        cycle_id = _as_int(params.get("cycle_id"), 0)
        window_start = str(params.get("window_start") or "").strip()
        window_end = str(params.get("window_end") or "").strip()
        if not window_start or not window_end:
            raise ValueError("window_start and window_end are required.")
        status, rows = _rest_select(
            "experiment",
            query={
                "cycle_id": f"eq.{cycle_id}",
                "or": f"(and(end_at.gte.{window_start},end_at.lt.{window_end}),status.eq.RUNNING)",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (experiments.for_retro_window): {status}"
            )
        return {"experiments": rows}

    if normalized == "retros.user":
        user_id = _as_int(params.get("user_id"), 0)
        cycle_id = _as_int(params.get("cycle_id"), 0)
        q = {
            "user_id": f"eq.{user_id}",
            "select": "*",
            "order": "week_start_date.desc",
        }
        if cycle_id:
            q["cycle_id"] = f"eq.{cycle_id}"
        status, rows = _rest_select("retrospective", query=q)
        if status >= 400:
            raise ValueError(f"Supabase API error (retros.user): {status}")
        return {"retros": rows}

    if normalized == "retros.team":
        manager_id = _as_int(params.get("manager_id"), 0)
        cycle_id = _as_int(params.get("cycle_id"), 0)
        status, members = _rest_select(
            "user",
            query={"manager_id": f"eq.{manager_id}", "select": "id", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (retros.team/users): {status}")
        member_ids = [
            str(_as_int(u.get("id"), 0)) for u in members if _as_int(u.get("id"), 0) > 0
        ]
        if not member_ids:
            return {"retros": []}
        q = {
            "user_id": f"in.({_in_clause_ids(member_ids)})",
            "select": "*",
            "order": "week_start_date.desc",
        }
        if cycle_id:
            q["cycle_id"] = f"eq.{cycle_id}"
        status, retros = _rest_select("retrospective", query=q)
        if status >= 400:
            raise ValueError(
                f"Supabase API error (retros.team/retrospective): {status}"
            )
        return {"retros": retros}

    if normalized == "alignments.context":
        objective_id = _as_int(params.get("objective_id"), 0)
        status, current_rows = _rest_select(
            "objective",
            query={"id": f"eq.{objective_id}", "select": "*", "limit": "1"},
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (alignments.context/objective): {status}"
            )
        if not current_rows:
            return {"parents": [], "children": [], "all_objectives": [], "edges": []}

        status, edge_rows = _rest_select(
            "alignment_edge",
            query={
                "or": f"(parent_id.eq.{objective_id},child_id.eq.{objective_id})",
                "select": "id,parent_id,child_id,alignment_type",
                "order": "id.asc",
            },
        )
        if status >= 400:
            raise ValueError(f"Supabase API error (alignments.context/edges): {status}")

        parent_ids = sorted(
            {
                int(e.get("parent_id") or 0)
                for e in edge_rows
                if int(e.get("child_id") or 0) == objective_id
                and int(e.get("parent_id") or 0) > 0
            }
        )
        child_ids = sorted(
            {
                int(e.get("child_id") or 0)
                for e in edge_rows
                if int(e.get("parent_id") or 0) == objective_id
                and int(e.get("child_id") or 0) > 0
            }
        )

        parents: list[dict[str, Any]] = []
        if parent_ids:
            status, rows = _rest_select(
                "objective",
                query={
                    "id": f"in.({_in_clause_ids([str(v) for v in parent_ids])})",
                    "select": "*",
                    "order": "id.asc",
                },
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (alignments.context/parents): {status}"
                )
            parents = [_decorate_node_row(r, table="objective") for r in rows]

        children: list[dict[str, Any]] = []
        if child_ids:
            status, rows = _rest_select(
                "objective",
                query={
                    "id": f"in.({_in_clause_ids([str(v) for v in child_ids])})",
                    "select": "*",
                    "order": "id.asc",
                },
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (alignments.context/children): {status}"
                )
            children = [_decorate_node_row(r, table="objective") for r in rows]

        status, all_rows = _rest_select(
            "objective",
            query={"id": f"neq.{objective_id}", "select": "*", "order": "id.asc"},
        )
        if status >= 400:
            raise ValueError(
                f"Supabase API error (alignments.context/all_objectives): {status}"
            )
        all_objectives = [_decorate_node_row(r, table="objective") for r in all_rows]

        edges = [
            {
                "id": _as_int(edge.get("id"), 0),
                "parent_id": _as_int(edge.get("parent_id"), 0),
                "child_id": _as_int(edge.get("child_id"), 0),
                "alignment_type": str(edge.get("alignment_type") or "SUPPORTS"),
            }
            for edge in edge_rows
            if _as_int(edge.get("id"), 0) > 0
        ]

        # Fetch all goals for the cross-hierarchy parent link dropdown
        status, goal_rows = _rest_select(
            "goal",
            query={"select": "id,title", "order": "id.asc"},
        )
        available_goals = [
            {"id": _as_int(g.get("id"), 0), "title": str(g.get("title") or "")}
            for g in (goal_rows if status < 400 else [])
            if _as_int(g.get("id"), 0) > 0
        ]

        # Fetch all key results for the cross-hierarchy child link dropdown
        status, kr_rows = _rest_select(
            "key_result",
            query={"select": "id,title", "order": "id.asc"},
        )
        available_key_results = [
            {"id": _as_int(kr.get("id"), 0), "title": str(kr.get("title") or "")}
            for kr in (kr_rows if status < 400 else [])
            if _as_int(kr.get("id"), 0) > 0
        ]

        # Fetch existing objective alignment links
        status, link_rows = _rest_select(
            "objective_alignment_link",
            query={
                "objective_id": f"eq.{objective_id}",
                "select": "*",
                "order": "id.asc",
            },
        )
        objective_links = [
            {
                "id": _as_int(lnk.get("id"), 0),
                "objective_id": _as_int(lnk.get("objective_id"), 0),
                "linked_entity_type": str(lnk.get("linked_entity_type") or ""),
                "linked_entity_id": _as_int(lnk.get("linked_entity_id"), 0),
                "direction": str(lnk.get("direction") or ""),
                "created_at": lnk.get("created_at"),
                "created_by": lnk.get("created_by"),
            }
            for lnk in (link_rows if status < 400 else [])
            if _as_int(lnk.get("id"), 0) > 0
        ]

        # Filter goals and KRs to only unlinked ones
        # Also exclude the current objective's parent goal (linked via FK)
        parent_goal_id = None
        if current_rows:
            parent_goal_id = _as_int(current_rows[0].get("goal_id"), 0) or None
        linked_goal_ids = {
            lnk["linked_entity_id"]
            for lnk in objective_links
            if lnk["linked_entity_type"] == "goal"
        }
        if parent_goal_id:
            linked_goal_ids.add(parent_goal_id)
        # Exclude KRs that are children of this objective (linked via FK)
        linked_kr_ids = {
            lnk["linked_entity_id"]
            for lnk in objective_links
            if lnk["linked_entity_type"] == "key_result"
        }
        status, child_kr_rows = _rest_select(
            "key_result",
            query={
                "objective_id": f"eq.{objective_id}",
                "select": "id",
                "limit": "500",
            },
        )
        if status < 400:
            for kr in child_kr_rows:
                kr_id = _as_int(kr.get("id"), 0)
                if kr_id:
                    linked_kr_ids.add(kr_id)
        available_goals = [g for g in available_goals if g["id"] not in linked_goal_ids]
        available_key_results = [
            kr for kr in available_key_results if kr["id"] not in linked_kr_ids
        ]

        return {
            "parents": parents,
            "children": children,
            "all_objectives": all_objectives,
            "edges": edges,
            "available_goals": available_goals,
            "available_key_results": available_key_results,
            "objective_links": objective_links,
        }

    if normalized == "mindmap.root":
        node_id = _as_int(params.get("node_id"), 0)
        resolved_node_type = str(params.get("node_type") or "").strip().upper() or None

        if not resolved_node_type:
            for table, label in (
                ("goal", "GOAL"),
                ("objective", "OBJECTIVE"),
                ("key_result", "KEY_RESULT"),
                ("task", "TASK"),
            ):
                status, rows = _rest_select(
                    table,
                    query={"id": f"eq.{node_id}", "select": "id", "limit": "1"},
                )
                if status >= 400:
                    raise ValueError(
                        f"Supabase API error (mindmap.root/detect/{table}): {status}"
                    )
                if rows:
                    resolved_node_type = label
                    break
        if not resolved_node_type:
            return {"node": None, "node_type": None}

        if resolved_node_type == "GOAL":
            status, goal_rows = _rest_select(
                "goal",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/goal): {status}")
            if not goal_rows:
                return {"node": None, "node_type": resolved_node_type}
            goal = _decorate_node_row(goal_rows[0], table="goal")
            status, objectives = _rest_select(
                "objective",
                query={"goal_id": f"eq.{node_id}", "select": "*", "order": "id.asc"},
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (mindmap.root/goal.objectives): {status}"
                )
            goal["objectives"] = [
                _decorate_node_row(r, table="objective") for r in objectives
            ]
            return {"node": goal, "node_type": resolved_node_type}

        if resolved_node_type == "OBJECTIVE":
            status, objective_rows = _rest_select(
                "objective",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (mindmap.root/objective): {status}"
                )
            if not objective_rows:
                return {"node": None, "node_type": resolved_node_type}
            objective = _decorate_node_row(objective_rows[0], table="objective")
            status, krs = _rest_select(
                "key_result",
                query={
                    "objective_id": f"eq.{node_id}",
                    "select": "*",
                    "order": "id.asc",
                },
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (mindmap.root/objective.krs): {status}"
                )
            objective["key_results"] = [
                _decorate_node_row(r, table="key_result") for r in krs
            ]
            return {"node": objective, "node_type": resolved_node_type}

        if resolved_node_type == "KEY_RESULT":
            status, kr_rows = _rest_select(
                "key_result",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/kr): {status}")
            if not kr_rows:
                return {"node": None, "node_type": resolved_node_type}
            kr = _decorate_node_row(kr_rows[0], table="key_result")
            status, tasks = _rest_select(
                "task",
                query={
                    "key_result_id": f"eq.{node_id}",
                    "select": "*",
                    "order": "id.asc",
                },
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (mindmap.root/kr.tasks): {status}"
                )
            kr["tasks"] = [_decorate_node_row(r, table="task") for r in tasks]
            return {"node": kr, "node_type": resolved_node_type}

        if resolved_node_type == "TASK":
            status, task_rows = _rest_select(
                "task",
                query={"id": f"eq.{node_id}", "select": "*", "limit": "1"},
            )
            if status >= 400:
                raise ValueError(f"Supabase API error (mindmap.root/task): {status}")
            if not task_rows:
                return {"node": None, "node_type": resolved_node_type}
            task = _decorate_node_row(task_rows[0], table="task")
            status, logs = _rest_select(
                "work_log",
                query={
                    "task_id": f"eq.{node_id}",
                    "select": "id,task_id,start_time,end_time,duration_minutes,summary,note",
                    "order": "start_time.desc",
                },
            )
            if status >= 400:
                raise ValueError(
                    f"Supabase API error (mindmap.root/task.work_logs): {status}"
                )
            task["work_logs"] = logs
            return {"node": task, "node_type": resolved_node_type}

    raise NotImplementedError(
        f"Read query kind '{normalized}' is not implemented in supabase_api mode yet."
    )
