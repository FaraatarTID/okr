from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import time
from typing import Any

from backend_app.data_access_mode import notify_tcp_db_failure, resolve_read_mode
from src.services.app_shell_runtime import (
    serialize_cycle,
    serialize_user,
    serialize_weekly_plan,
)
from src.observability import record_timing

_RPC_FALLBACK_WARNED = False


@contextmanager
def _timed_phase(name: str):
    started_at = time.perf_counter()
    try:
        yield
    finally:
        record_timing(name, (time.perf_counter() - started_at) * 1000)


def get_read_query_allowed_kinds() -> set[str]:
    return {
        "audit.summary",
        "users.by_username",
        "users.by_id",
        "users.all",
        "users.team_members",
        "teams.all",
        "teams.by_id",
        "cycles.all",
        "cycles.active",
        "weekly_plan.active",
        "node.get",
        "node.detect_type",
        "krs.by_cycle",
        "krs.needing_checkin",
        "experiments.for_kr",
        "experiments.active_for_kr",
        "experiments.for_retro_window",
        "ritual.snapshot",
        "retros.user",
        "retros.team",
        "tasks.by_cycle",
        "work_logs.by_range",
        "work_logs.by_task",
        "alignments.context",
        "mindmap.root",
        "mindmap.children",
    }


def _validate_supabase_read_scope(
    *, kind: str, params: dict, actor: str, main: Any
) -> None:
    """Apply actor scope before service-role REST reads are dispatched."""
    scope = main._resolve_scope_for_actor(actor)
    user_id_kinds = {
        "users.by_id",
        "weekly_plan.active",
        "retros.user",
        "work_logs.by_range",
    }
    if kind in user_id_kinds:
        main._require_allowed_user_id(
            scope, main._coerce_int(params.get("user_id"), field_name="user_id")
        )
    elif kind == "users.by_username":
        main._require_allowed_username(
            scope, str(params.get("username") or "").strip()
        )
    elif kind in {"node.get"}:
        owner_id = main._resolve_goal_owner_id_for_node_via_supabase(
            node_type=str(params.get("node_type") or "").strip(),
            node_id=main._coerce_int(params.get("node_id"), field_name="node_id"),
            actor=actor,
        )
        if owner_id is None:
            raise main.HTTPException(status_code=404, detail="Node not found.")
        main._require_allowed_user_id(scope, owner_id)
    elif kind in {"experiments.for_kr", "experiments.active_for_kr"}:
        owner_id = main._resolve_goal_owner_id_for_node_via_supabase(
            node_type="KEY_RESULT",
            node_id=main._coerce_int(
                params.get("key_result_id"), field_name="key_result_id"
            ),
            actor=actor,
        )
        if owner_id is None:
            raise main.HTTPException(status_code=404, detail="Key result not found.")
        main._require_allowed_user_id(scope, owner_id)


def read_query_payload(
    *,
    kind: str,
    params: dict,
    actor: str,
    main: Any,
    allowed_kinds: set[str] | None = None,
) -> dict:
    kind = str(kind or "").strip()
    allowed = allowed_kinds if allowed_kinds is not None else get_read_query_allowed_kinds()
    user_serializer = getattr(main, "_serialize_user", serialize_user)
    if kind not in allowed:
        raise main.HTTPException(
            status_code=400,
            detail=f"Unsupported read query kind: {kind}",
        )

    if kind == "ritual.snapshot":
        cycle_id = main._coerce_int(params.get("cycle_id"), field_name="cycle_id")
        user_id = params.get("user_id")
        use_https = resolve_read_mode() == "supabase_api"
        if use_https:
            _validate_supabase_read_scope(
                kind="weekly_plan.active",
                params={"user_id": user_id},
                actor=actor,
                main=main,
            )
        review_params = {
            "cycle_id": cycle_id,
            "window_start": params.get("window_start"),
            "window_end": params.get("window_end"),
        }
        query_params = {
            # krs.needing_checkin uses the actor username as user_id for its
            # existing authorization and query contract.
            "user_id": actor,
            "cycle_id": cycle_id,
            "days_threshold": params.get("days_threshold", 7),
        }
        if use_https:
            # Preferred path: single authorized RPC (one round trip).
            rpc_params = {
                "actor_username": actor,
                "cycle_id": cycle_id,
                "days_threshold": params.get("days_threshold", 7),
                "date": params.get("date"),
                "window_start": params.get("window_start"),
                "window_end": params.get("window_end"),
            }
            try:
                snapshot_payload = main.read_query_via_supabase_api(
                    kind="ritual.snapshot",
                    params=rpc_params,
                    actor=actor,
                )
                snapshot = snapshot_payload.get("snapshot") or {}
                return {
                    "key_results": snapshot.get("key_results", []),
                    "weekly_plan": snapshot.get("weekly_plan"),
                    "retros": snapshot.get("retros", []),
                    "work_logs": snapshot.get("work_logs", []),
                    "experiments": snapshot.get("experiments", []),
                }
            except ValueError as exc:
                detail = str(exc)
                # Missing function (migration not applied): fall back to the
                # bounded concurrent fan-out below. Latched per process via a
                # module flag so the warning logs only once.
                if "42883" in detail or "fn_ritual_snapshot" in detail:
                    global _RPC_FALLBACK_WARNED
                    if not _RPC_FALLBACK_WARNED:
                        _RPC_FALLBACK_WARNED = True
                        main._LOGGER.warning(
                            "ritual.snapshot RPC missing (42883); using concurrent "
                            "fan-out fallback until migration y2d3e4f5a6b7 runs."
                        )
                    # Fall through to the fan-out path below.
                else:
                    # Validation errors from the RPC parameter contract
                    # propagate as client errors.
                    raise main.HTTPException(status_code=400, detail=detail) from exc
            queries = [
                ("krs.needing_checkin", query_params),
                (
                    "weekly_plan.active",
                    {"user_id": user_id, "date": params.get("date")},
                ),
                ("retros.user", {"user_id": user_id, "cycle_id": cycle_id}),
                (
                    "work_logs.by_range",
                    {
                        "user_id": user_id,
                        "start_date": params.get("window_start"),
                        "end_date": params.get("window_end"),
                    },
                ),
                ("experiments.for_retro_window", review_params),
            ]

            def _run_query(item: tuple[str, dict]) -> dict:
                query_kind, query_values = item
                return main.read_query_via_supabase_api(
                    kind=query_kind,
                    params=query_values,
                    actor=actor,
                )

            # Bound concurrency: one snapshot creates at most five upstream
            # requests, but avoids serially paying each Supabase RTT.
            with ThreadPoolExecutor(max_workers=len(queries)) as executor:
                results = list(executor.map(_run_query, queries))
            return {
                "key_results": results[0].get("key_results", []),
                "weekly_plan": results[1].get("weekly_plan"),
                "retros": results[2].get("retros", []),
                "work_logs": results[3].get("work_logs", []),
                "experiments": results[4].get("experiments", []),
            }
        return {
            "key_results": read_query_payload(
                kind="krs.needing_checkin", params=query_params, actor=actor,
                main=main, allowed_kinds=allowed,
            ).get("key_results", []),
            "weekly_plan": read_query_payload(
                kind="weekly_plan.active",
                params={"user_id": user_id, "date": params.get("date")},
                actor=actor, main=main, allowed_kinds=allowed,
            ).get("weekly_plan"),
            "retros": read_query_payload(
                kind="retros.user",
                params={"user_id": user_id, "cycle_id": cycle_id},
                actor=actor, main=main, allowed_kinds=allowed,
            ).get("retros", []),
            "work_logs": read_query_payload(
                kind="work_logs.by_range",
                params={
                    "user_id": user_id,
                    "start_date": params.get("window_start"),
                    "end_date": params.get("window_end"),
                },
                actor=actor, main=main, allowed_kinds=allowed,
            ).get("work_logs", []),
            "experiments": read_query_payload(
                kind="experiments.for_retro_window", params=review_params,
                actor=actor, main=main, allowed_kinds=allowed,
            ).get("experiments", []),
        }

    if resolve_read_mode() == "supabase_api":
        with _timed_phase("scope"):
            _validate_supabase_read_scope(
                kind=kind,
                params=params,
                actor=actor,
                main=main,
            )
        try:
            with _timed_phase("handler"):
                return main.read_query_via_supabase_api(
                    kind=str(kind or "").strip(),
                    params=dict(params or {}),
                    actor=str(actor or "").strip(),
                )
        except NotImplementedError as exc:
            raise main.HTTPException(status_code=501, detail=str(exc)) from exc
        except Exception as exc:
            # HTTPS fallback itself failing is a real upstream outage.
            if str(type(exc).__name__) in {
                "SupabaseTransportError",
                "CircuitOpenError",
            }:
                raise main.HTTPException(
                    status_code=503,
                    detail="Upstream data service temporarily unavailable.",
                ) from exc
            raise

    try:
        scope = main._resolve_scope_for_actor(actor)
    except Exception:
        # TCP scope resolution failed (e.g. connection refused); if HTTPS
        # fallback is available, retry the whole read over HTTPS.
        notify_tcp_db_failure()
        if resolve_read_mode() == "supabase_api":
            return read_query_payload(
                kind=kind, params=params, actor=actor,
                main=main, allowed_kinds=allowed,
            )
        raise

    if kind == "audit.summary":
        if not bool(scope.get("is_admin", False)):
            raise main.HTTPException(status_code=403, detail="Admin privileges required.")
        days = main._coerce_int(params.get("days", 30), field_name="days")
        if days < 1 or days > 365:
            raise main.HTTPException(
                status_code=400, detail="days must be between 1 and 365."
            )
        recent_limit = main._coerce_int(
            params.get("recent_limit", 20), field_name="recent_limit"
        )
        if recent_limit < 1 or recent_limit > 100:
            raise main.HTTPException(
                status_code=400, detail="recent_limit must be between 1 and 100."
            )
        filters: dict[str, Any] = {}
        for key in (
            "action",
            "entity",
            "actor",
            "actor_role",
            "target_type",
            "correlation_id",
            "request_id",
        ):
            value = params.get(key)
            if value is not None and str(value).strip():
                filters[key] = str(value).strip()
        for key in (
            "actor_user_id",
            "actor_team_id",
            "target_id",
            "target_owner_id",
            "target_team_id",
        ):
            if params.get(key) is not None:
                filters[key] = main._coerce_int(params.get(key), field_name=key)
        if params.get("result") is not None and str(params.get("result")).strip():
            filters["result"] = str(params.get("result")).strip()
        with main.get_session_context() as session:
            return main.summarize_audit_events(
                session,
                days=days,
                recent_limit=recent_limit,
                **filters,
            )

    if kind == "users.by_username":
        username = str(params.get("username") or "").strip()
        if not username:
            return {"user": None}
        user = main.get_user_by_username(username)
        user_payload = user_serializer(user)
        if user_payload is None:
            return {"user": None}
        main._require_allowed_user_id(scope, int(user_payload["id"]))
        return {"user": user_payload}

    if kind == "users.by_id":
        user_id = main._coerce_int(params.get("user_id"), field_name="user_id")
        main._require_allowed_user_id(scope, user_id)
        return {"user": user_serializer(main.get_user_by_id(user_id))}

    if kind == "users.all":
        users = list(main.get_all_users() or [])
        owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
        if not bool(scope.get("is_admin", False)):
            users = [
                user for user in users if int(getattr(user, "id", 0) or 0) in owner_ids
            ]
        return {
            "users": [
                payload
                for payload in (user_serializer(user) for user in users)
                if payload is not None
            ]
        }

    if kind == "users.team_members":
        manager_id = main._coerce_int(params.get("manager_id"), field_name="manager_id")
        main._require_allowed_user_id(scope, manager_id)
        users = list(main.get_team_members(manager_id) or [])
        owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
        if not bool(scope.get("is_admin", False)):
            users = [
                user for user in users if int(getattr(user, "id", 0) or 0) in owner_ids
            ]
        return {
            "users": [
                payload
                for payload in (user_serializer(user) for user in users)
                if payload is not None
            ]
        }

    if kind == "teams.all":
        teams = list(main.get_all_teams() or [])
        return {
            "teams": [
                payload
                for payload in (main._serialize_team(team) for team in teams)
                if payload is not None
            ]
        }

    if kind == "teams.by_id":
        team_id = main._coerce_int(params.get("team_id"), field_name="team_id")
        return {"team": main._serialize_team(main.get_team_by_id(team_id))}

    if kind == "cycles.all":
        cycles = main._visible_cycles_for_scope(scope, list(main.get_all_cycles() or []))
        if main._scope_role(scope) == "member":
            if not cycles:
                cycles = main._visible_cycles_for_scope(
                    scope, list(main.get_active_cycles() or [])
                )
            primary = main._pick_primary_active_cycle(
                [c for c in cycles if bool(getattr(c, "is_active", False))],
                scope,
            )
            cycles = [primary] if primary is not None else []
        return {
            "cycles": [
                payload
                for payload in (serialize_cycle(cycle) for cycle in cycles)
                if payload is not None
            ]
        }

    if kind == "cycles.active":
        cycles = main._visible_cycles_for_scope(scope, list(main.get_active_cycles() or []))
        if main._scope_role(scope) == "member":
            primary = main._pick_primary_active_cycle(cycles, scope)
            cycles = [primary] if primary is not None else []
        return {
            "cycles": [
                payload
                for payload in (serialize_cycle(cycle) for cycle in cycles)
                if payload is not None
            ]
        }

    if kind == "weekly_plan.active":
        user_id = main._coerce_int(params.get("user_id"), field_name="user_id")
        main._require_allowed_user_id(scope, user_id)
        date_value = (
            main._coerce_datetime(params.get("date"), field_name="date")
            if params.get("date")
            else None
        )
        plan = main.get_active_weekly_plan(user_id, date=date_value)
        return {"weekly_plan": serialize_weekly_plan(plan)}

    if kind == "node.get":
        node_id = main._coerce_int(params.get("node_id"), field_name="node_id")
        requested_node_type = main._normalize_node_type(str(params.get("node_type") or ""))
        node = main.get_node(node_id, requested_node_type, actor_username=actor)
        payload = main._serialize_node_for_type(requested_node_type, node)
        if payload is None:
            return {"node": None}
        owner_id = main._node_owner_id(requested_node_type, payload)
        if owner_id is not None:
            main._require_allowed_user_id(scope, owner_id)
        return {"node": payload}

    if kind == "node.detect_type":
        node_id = main._coerce_int(params.get("node_id"), field_name="node_id")
        for label in ("TASK", "KEY_RESULT", "OBJECTIVE", "GOAL"):
            candidate = main.get_node(node_id, label, actor_username=actor)
            if candidate:
                return {"node_type": label}
        return {"node_type": None}

    if kind == "krs.by_cycle":
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope,
            main._coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise main.HTTPException(status_code=400, detail="cycle_id is required.")
        limit_raw = params.get("limit")
        offset_raw = params.get("offset", 0)
        limit = (
            main._coerce_int(limit_raw, field_name="limit")
            if limit_raw is not None
            else None
        )
        if limit is not None and (limit < 1 or limit > 500):
            raise main.HTTPException(
                status_code=400, detail="limit must be between 1 and 500."
            )
        offset = main._coerce_int(offset_raw, field_name="offset")
        krs = list(main.get_all_krs_by_cycle(cycle_id, limit=limit, offset=offset) or [])
        if not bool(scope.get("is_admin", False)):
            owner_ids = {int(value) for value in (scope.get("owner_ids") or set())}
            filtered = []
            for kr in krs:
                goal_owner_id = getattr(
                    getattr(getattr(kr, "objective", None), "goal", None),
                    "owner_id",
                    None,
                )
                if goal_owner_id is not None and int(goal_owner_id) in owner_ids:
                    filtered.append(kr)
            krs = filtered
        return {
            "key_results": [
                payload
                for payload in (
                    main._serialize_key_result(
                        key_result,
                        include_tasks=False,
                        include_check_ins=False,
                        include_objective=True,
                    )
                    for key_result in krs
                )
                if payload is not None
            ]
        }

    if kind == "tasks.by_cycle":
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope,
            main._coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise main.HTTPException(status_code=400, detail="cycle_id is required.")
        limit_raw = params.get("limit")
        offset_raw = params.get("offset", 0)
        limit = (
            main._coerce_int(limit_raw, field_name="limit")
            if limit_raw is not None
            else None
        )
        if limit is not None and (limit < 1 or limit > 500):
            raise main.HTTPException(
                status_code=400, detail="limit must be between 1 and 500."
            )
        offset = main._coerce_int(offset_raw, field_name="offset")
        tasks = list(main.get_all_tasks_by_cycle(cycle_id, limit=limit, offset=offset) or [])
        tasks = main._filter_tasks_for_scope(tasks, scope)
        return {
            "tasks": [
                payload
                for payload in (
                    main._serialize_task(
                        task,
                        include_key_result=True,
                        include_work_logs=False,
                    )
                    for task in tasks
                )
                if payload is not None
            ]
        }

    if kind == "work_logs.by_range":
        user_id = main._coerce_int(params.get("user_id"), field_name="user_id")
        main._require_allowed_user_id(scope, user_id)
        start_date = main._coerce_datetime(
            params.get("start_date"),
            field_name="start_date",
        )
        end_date = main._coerce_datetime(
            params.get("end_date"),
            field_name="end_date",
        )
        if start_date and end_date:
            range_days = (end_date - start_date).days
            if range_days > 90:
                raise main.HTTPException(
                    status_code=400,
                    detail="Date range must not exceed 90 days.",
                )
        logs = list(main.get_work_logs_by_date_range(user_id, start_date, end_date) or [])
        return {
            "work_logs": [
                payload
                for payload in (
                    main._serialize_work_log(work_log, include_task=True)
                    for work_log in logs
                )
                if payload is not None
            ]
        }

    if kind == "work_logs.by_task":
        task_id = main._coerce_int(params.get("task_id"), field_name="task_id")
        task_node = main.get_node(task_id, "TASK", actor_username=actor)
        if not task_node:
            return {"work_logs": []}
        work_logs = sorted(
            list(getattr(task_node, "work_logs", []) or []),
            key=lambda row: getattr(row, "start_time", main.datetime.min),
            reverse=True,
        )
        return {
            "work_logs": [
                payload
                for payload in (
                    main._serialize_work_log(work_log, include_task=False)
                    for work_log in work_logs
                )
                if payload is not None
            ]
        }

    if kind == "krs.needing_checkin":
        username = str(params.get("user_id") or "").strip()
        if not username:
            raise main.HTTPException(status_code=400, detail="user_id is required.")
        main._require_allowed_username(scope, username)
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope,
            main._coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise main.HTTPException(status_code=400, detail="cycle_id is required.")
        days_threshold = main._coerce_int(
            params.get("days_threshold", 7),
            field_name="days_threshold",
        )
        krs = list(
            main.get_krs_needing_checkin(
                user_id=username,
                cycle_id=cycle_id,
                days_threshold=days_threshold,
            )
            or []
        )
        return {
            "key_results": [
                payload
                for payload in (
                    main._serialize_key_result(
                        key_result,
                        include_tasks=False,
                        include_check_ins=False,
                        include_objective=False,
                    )
                    for key_result in krs
                )
                if payload is not None
            ]
        }

    if kind == "experiments.active_for_kr":
        key_result_id = main._coerce_int(
            params.get("key_result_id"),
            field_name="key_result_id",
        )
        experiments = list(
            main.get_active_experiments_for_kr(
                key_result_id=key_result_id,
                actor_username=actor,
            )
            or []
        )
        return {
            "experiments": [
                payload
                for payload in (
                    main._serialize_experiment(experiment) for experiment in experiments
                )
                if payload is not None
            ]
        }

    if kind == "experiments.for_kr":
        key_result_id = main._coerce_int(
            params.get("key_result_id"),
            field_name="key_result_id",
        )
        experiments = list(
            main.list_experiments_for_kr(
                key_result_id=key_result_id,
                actor_username=actor,
            )
            or []
        )
        return {
            "experiments": [
                payload
                for payload in (
                    main._serialize_experiment(experiment) for experiment in experiments
                )
                if payload is not None
            ]
        }

    if kind == "experiments.for_retro_window":
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope,
            main._coerce_int(params.get("cycle_id"), field_name="cycle_id"),
        )
        if cycle_id is None:
            raise main.HTTPException(status_code=400, detail="cycle_id is required.")
        window_start = main._coerce_datetime(
            params.get("window_start"),
            field_name="window_start",
        )
        window_end = main._coerce_datetime(
            params.get("window_end"),
            field_name="window_end",
        )
        experiments = list(
            main.list_experiments_for_retro_window(
                cycle_id=cycle_id,
                window_start=window_start,
                window_end=window_end,
                actor_username=actor,
            )
            or []
        )
        return {
            "experiments": [
                payload
                for payload in (
                    main._serialize_experiment(experiment) for experiment in experiments
                )
                if payload is not None
            ]
        }

    if kind == "retros.user":
        user_id = main._coerce_int(params.get("user_id"), field_name="user_id")
        main._require_allowed_user_id(scope, user_id)
        cycle_id_raw = params.get("cycle_id")
        requested_cycle_id = (
            main._coerce_int(cycle_id_raw, field_name="cycle_id")
            if cycle_id_raw is not None
            else None
        )
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope,
            requested_cycle_id,
            required=False,
        )
        retros = list(main.get_user_retrospectives(user_id=user_id, cycle_id=cycle_id) or [])
        return {
            "retros": [
                payload
                for payload in (
                    main._serialize_retro(retro, include_user=False) for retro in retros
                )
                if payload is not None
            ]
        }

    if kind == "retros.team":
        manager_id = main._coerce_int(params.get("manager_id"), field_name="manager_id")
        main._require_allowed_user_id(scope, manager_id)
        cycle_id_raw = params.get("cycle_id")
        requested_cycle_id = (
            main._coerce_int(cycle_id_raw, field_name="cycle_id")
            if cycle_id_raw is not None
            else None
        )
        cycle_id = main._resolve_effective_cycle_id_for_scope(
            scope,
            requested_cycle_id,
            required=False,
        )
        retros = list(main.get_team_retrospectives(manager_id=manager_id, cycle_id=cycle_id) or [])
        with main.get_session_context() as session:
            users_by_id: dict[int, Any] = {
                int(getattr(user, "id")): user
                for user in (
                    session.exec(
                        main.select(main.User).where(main.User.manager_id == int(manager_id))
                    ).all()
                )
                if getattr(user, "id", None) is not None
            }
        serialized_retros = []
        for retro in retros:
            payload = main._serialize_retro(retro, include_user=False)
            if payload is None:
                continue
            user_payload = user_serializer(users_by_id.get(int(payload.get("user_id") or 0)))
            payload["user"] = user_payload
            serialized_retros.append(payload)
        return {"retros": serialized_retros}

    if kind == "alignments.context":
        objective_id = main._coerce_int(
            params.get("objective_id"), field_name="objective_id"
        )
        objective_node = main.get_node(objective_id, "OBJECTIVE", actor_username=actor)
        if not objective_node:
            return {
                "parents": [],
                "children": [],
                "all_objectives": [],
                "edges": [],
                "available_goals": [],
                "available_key_results": [],
                "objective_links": [],
            }
        with main.get_session_context() as session:
            from src.domain.alignment import get_alignment_neighbors
            from src.models import ObjectiveAlignmentLink

            parents, children = get_alignment_neighbors(session, int(objective_id))
            edge_rows = list(
                session.exec(
                    main.select(main.AlignmentEdge).where(
                        (main.AlignmentEdge.parent_id == int(objective_id))
                        | (main.AlignmentEdge.child_id == int(objective_id))
                    )
                ).all()
            )
            all_objectives = list(
                session.exec(
                    main.select(main.Objective)
                    .where(main.Objective.id != int(objective_id))
                    .limit(500)
                ).all()
            )
            available_goals = list(session.exec(main.select(main.Goal).limit(500)).all())
            available_krs = list(session.exec(main.select(main.KeyResult).limit(500)).all())
            try:
                from src.models import ObjectiveAlignmentLink

                obj_links = list(
                    session.exec(
                        main.select(ObjectiveAlignmentLink).where(
                            ObjectiveAlignmentLink.objective_id == int(objective_id)
                        )
                    ).all()
                )
                # Filter to only unlinked entities
                # Also exclude the current objective's parent goal (linked via FK)
                parent_goal_id = None
                goal = getattr(objective_node, "goal", None)
                if goal:
                    parent_goal_id = getattr(goal, "id", None)
                linked_goal_ids = {
                    lnk.linked_entity_id
                    for lnk in obj_links
                    if lnk.linked_entity_type == "goal"
                }
                if parent_goal_id:
                    linked_goal_ids.add(parent_goal_id)
                # Exclude KRs that are children of this objective (linked via FK)
                linked_kr_ids = {
                    lnk.linked_entity_id
                    for lnk in obj_links
                    if lnk.linked_entity_type == "key_result"
                }
                child_krs = list(
                    session.exec(
                        main.select(main.KeyResult).where(
                            main.KeyResult.objective_id == int(objective_id)
                        )
                    ).all()
                )
                for kr in child_krs:
                    kr_id = getattr(kr, "id", None)
                    if kr_id:
                        linked_kr_ids.add(kr_id)
                available_goals = [
                    g
                    for g in available_goals
                    if getattr(g, "id", None) not in linked_goal_ids
                ]
                available_krs = [
                    kr
                    for kr in available_krs
                    if getattr(kr, "id", None) not in linked_kr_ids
                ]
            except Exception:
                main._LOGGER.warning(
                    "Failed to load alignment links for objective_id=%s; falling back to empty",
                    objective_id,
                    exc_info=True,
                )
                obj_links = []

        return {
            "parents": [
                payload
                for payload in (
                    main._serialize_objective(
                        parent,
                        include_key_results=False,
                        include_goal=False,
                    )
                    for parent in parents
                )
                if payload is not None
            ],
            "children": [
                payload
                for payload in (
                    main._serialize_objective(
                        child,
                        include_key_results=False,
                        include_goal=False,
                    )
                    for child in children
                )
                if payload is not None
            ],
            "all_objectives": [
                payload
                for payload in (
                    main._serialize_objective(
                        objective,
                        include_key_results=False,
                        include_goal=False,
                    )
                    for objective in all_objectives
                )
                if payload is not None
            ],
            "edges": [
                {
                    "id": int(getattr(edge, "id")),
                    "parent_id": int(getattr(edge, "parent_id")),
                    "child_id": int(getattr(edge, "child_id")),
                    "alignment_type": str(
                        main._enum_value(getattr(edge, "alignment_type", "SUPPORTS"))
                    ),
                }
                for edge in edge_rows
                if getattr(edge, "id", None) is not None
            ],
            "available_goals": [
                {
                    "id": int(getattr(g, "id")),
                    "title": str(getattr(g, "title", "") or ""),
                }
                for g in available_goals
                if getattr(g, "id", None) is not None
            ],
            "available_key_results": [
                {
                    "id": int(getattr(kr, "id")),
                    "title": str(getattr(kr, "title", "") or ""),
                }
                for kr in available_krs
                if getattr(kr, "id", None) is not None
            ],
            "objective_links": [
                {
                    "id": int(getattr(link, "id")),
                    "objective_id": int(getattr(link, "objective_id")),
                    "linked_entity_type": str(getattr(link, "linked_entity_type")),
                    "linked_entity_id": int(getattr(link, "linked_entity_id")),
                    "direction": str(getattr(link, "direction")),
                    "created_at": getattr(link, "created_at", None),
                    "created_by": getattr(link, "created_by", None),
                }
                for link in obj_links
                if getattr(link, "id", None) is not None
            ],
        }

    if kind == "mindmap.root":
        node_id = main._coerce_int(params.get("node_id"), field_name="node_id")
        node_type_raw = str(params.get("node_type") or "").strip()
        resolved_node_type = node_type_raw.upper() if node_type_raw else None
        if resolved_node_type is None:
            for label in ("GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"):
                candidate = main.get_node(node_id, label, actor_username=actor)
                if candidate:
                    resolved_node_type = label
                    break
        if not resolved_node_type:
            return {"node": None, "node_type": None}

        resolved_node_type = main._normalize_node_type(resolved_node_type)
        scoped_node = main.get_node(node_id, resolved_node_type, actor_username=actor)
        if not scoped_node:
            return {"node": None, "node_type": resolved_node_type}

        if resolved_node_type == "GOAL":
            full_goal = main.get_goal_tree(node_id)
            node_payload = main._serialize_goal(full_goal, include_objectives=True)
        elif resolved_node_type == "OBJECTIVE":
            node_payload = main._serialize_objective(
                scoped_node,
                include_key_results=True,
                include_goal=False,
            )
        elif resolved_node_type == "KEY_RESULT":
            node_payload = main._serialize_key_result(
                scoped_node,
                include_tasks=True,
                include_check_ins=False,
                include_objective=False,
            )
        elif resolved_node_type == "TASK":
            node_payload = main._serialize_task(
                scoped_node,
                include_key_result=False,
                include_work_logs=True,
            )
        else:
            node_payload = main._serialize_node_for_type(resolved_node_type, scoped_node)
        return {"node": node_payload, "node_type": resolved_node_type}

    raise main.HTTPException(status_code=404, detail="Unsupported read query kind.")


_ALLOWED_READ_QUERY_KINDS = get_read_query_allowed_kinds()


__all__ = ["_ALLOWED_READ_QUERY_KINDS", "get_read_query_allowed_kinds", "read_query_payload"]
