"""Read-query orchestration service for CRUD facade."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from src import (
    crud_checkin_helpers,
    crud_cycle_helpers,
    crud_data_helpers,
    crud_auth_helpers,
    crud_experiment_helpers,
    crud_query_helpers,
    crud_reflection_helpers,
    crud_team_helpers,
)
from src import crud_core_helpers
from src.models import (
    Cycle,
    Experiment,
    User,
    KeyResult,
    Retrospective,
    Task,
    Team,
    WeeklyPlan,
)


def backend_read_proxy_enabled_from_crud(*, crud_module) -> bool:
    return crud_core_helpers.backend_mutation_proxy_enabled_from_crud(
        crud_module=crud_module
    )


def resolve_backend_actor_from_crud(
    *, crud_module, actor_username: Optional[str] = None
) -> str:
    from src.services import backend_client

    return str(
        backend_client.resolve_actor_username(actor_username=actor_username)
    ).strip()


def raise_backend_read_error_from_crud(
    *, crud_module, operation: str, payload: dict[str, Any]
) -> None:
    message = str(
        payload.get("error") or f"Backend read failed for {operation}."
    ).strip()
    try:
        code = int(payload.get("status_code") or 0)
    except Exception:
        code = 0
    if code in {401, 403}:
        raise PermissionError(message)
    if code == 404:
        raise ValueError(message or "Not found.")
    raise ValueError(message)


def backend_read_result_or_raise_from_crud(
    *, crud_module, operation: str, result
) -> Any:
    if isinstance(result, dict) and "error" in result:
        raise_backend_read_error_from_crud(
            crud_module=crud_module,
            operation=operation,
            payload=result,
        )
    return result


def get_krs_needing_checkin_from_crud(
    *,
    crud_module,
    user_id: str,
    cycle_id: int,
    days_threshold: int = 7,
) -> List[KeyResult]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        username = str(user_id or "").strip()
        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_krs_needing_checkin(
            username=username,
            cycle_id=int(cycle_id),
            days_threshold=int(days_threshold),
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_krs_needing_checkin",
                result=backend_result,
            )
            or []
        )
    return crud_checkin_helpers.get_krs_needing_checkin_from_crud(
        crud_module=crud_module,
        username=user_id,
        cycle_id=cycle_id,
        days_threshold=days_threshold,
    )


def get_check_ins_from_crud(*, crud_module, kr_id: int):
    return crud_checkin_helpers.get_check_ins_from_crud(
        crud_module=crud_module,
        kr_id=kr_id,
    )


def get_user_goals_simple_from_crud(
    *, crud_module, user_id: str, cycle_id: Optional[int] = None
) -> List[Any]:
    return crud_auth_helpers.get_user_goals_simple_from_crud(
        crud_module=crud_module,
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_dashboard_data_from_crud(
    *, crud_module, user_id: str, cycle_id: Optional[int] = None
):
    return crud_query_helpers.get_dashboard_data_from_crud(
        crud_module=crud_module,
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_goal_tree_from_crud(*, crud_module, goal_id: int):
    return crud_query_helpers.get_goal_tree_from_crud(
        crud_module=crud_module,
        goal_id=goal_id,
    )


def get_hours_by_goal_from_crud(*, user_id: int, days: int = 7) -> dict:
    return crud_data_helpers.get_hours_by_goal_from_crud(user_id=user_id, days=days)


def get_daily_work_trend_from_crud(*, user_id: int, days: int = 7) -> dict:
    return crud_data_helpers.get_daily_work_trend_from_crud(user_id=user_id, days=days)


def get_active_experiments_for_kr_from_crud(
    *,
    crud_module,
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(
            crud_module=crud_module,
            actor_username=actor_username,
        )
        backend_result = backend_client.read_active_experiments_for_kr(
            int(key_result_id),
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_active_experiments_for_kr",
                result=backend_result,
            )
            or []
        )
    return crud_experiment_helpers.get_active_experiments_for_kr_from_crud(
        crud_module=crud_module,
        key_result_id=key_result_id,
        actor_username=actor_username,
    )


def get_user_by_username_from_crud(*, crud_module, username: str) -> Optional[User]:
    return crud_auth_helpers.get_user_by_username_from_crud(
        crud_module=crud_module,
        username=username,
    )


def get_user_by_id_from_crud(*, crud_module, user_id: int) -> Optional[User]:
    return crud_auth_helpers.get_user_by_id_from_crud(
        crud_module=crud_module,
        user_id=user_id,
    )


def get_all_users_from_crud(*, crud_module) -> List[User]:
    return list(crud_auth_helpers.get_all_users_from_crud(crud_module=crud_module))


def get_team_members_from_crud(*, crud_module, manager_id: int) -> List[User]:
    return crud_auth_helpers.get_team_members_from_crud(
        crud_module=crud_module,
        manager_id=manager_id,
    )


def list_experiments_for_kr_from_crud(
    *,
    crud_module,
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    return crud_experiment_helpers.list_experiments_for_kr_from_crud(
        crud_module=crud_module,
        key_result_id=key_result_id,
        actor_username=actor_username,
    )


def list_experiments_for_retro_window_from_crud(
    *,
    crud_module,
    cycle_id: int,
    window_start,
    window_end,
    actor_username: str,
) -> List[Experiment]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(
            crud_module=crud_module,
            actor_username=actor_username,
        )
        backend_result = backend_client.read_experiments_for_retro_window(
            cycle_id=int(cycle_id),
            window_start=window_start,
            window_end=window_end,
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="list_experiments_for_retro_window",
                result=backend_result,
            )
            or []
        )
    return crud_experiment_helpers.list_experiments_for_retro_window_from_crud(
        crud_module=crud_module,
        cycle_id=cycle_id,
        window_start=window_start,
        window_end=window_end,
        actor_username=actor_username,
    )


def get_active_cycles_from_crud(*, crud_module) -> List[Cycle]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_active_cycles(actor_username=actor)
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_active_cycles",
                result=backend_result,
            )
            or []
        )
    return crud_cycle_helpers.get_active_cycles_from_crud(
        crud_module=crud_module,
    )


def get_all_cycles_from_crud(*, crud_module) -> List[Cycle]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_all_cycles(actor_username=actor)
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_all_cycles",
                result=backend_result,
            )
            or []
        )
    return crud_cycle_helpers.get_all_cycles_from_crud(
        crud_module=crud_module,
    )


def get_node_from_crud(
    *,
    crud_module,
    node_id: int,
    node_type: str,
    actor_username: Optional[str] = None,
):
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(
            crud_module=crud_module,
            actor_username=actor_username,
        )
        backend_result = backend_client.read_node(
            int(node_id),
            node_type,
            actor_username=actor,
        )
        return backend_read_result_or_raise_from_crud(
            crud_module=crud_module,
            operation="get_node",
            result=backend_result,
        )
    return crud_query_helpers.get_node_from_crud(
        crud_module=crud_module,
        node_id=node_id,
        node_type=node_type,
        actor_username=actor_username,
    )


def get_leadership_metrics_from_crud(
    *,
    crud_module,
    usernames,
    cycle_id: int,
):
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services.backend_client import fetch_leadership_metrics

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = fetch_leadership_metrics(
            cycle_id=int(cycle_id),
            usernames=[str(username).strip() for username in (usernames or [])],
            actor_username=actor,
        )
        return backend_read_result_or_raise_from_crud(
            crud_module=crud_module,
            operation="get_leadership_metrics",
            result=backend_result,
        )
    return crud_data_helpers.get_leadership_metrics_from_crud(
        usernames=usernames,
        cycle_id=cycle_id,
    )


def get_work_logs_by_date_range_from_crud(
    *,
    crud_module,
    user_id: int,
    start_date,
    end_date,
) -> List[Any]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_work_logs_by_range(
            user_id=int(user_id),
            start_date=start_date,
            end_date=end_date,
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_work_logs_by_date_range",
                result=backend_result,
            )
            or []
        )
    return crud_data_helpers.get_work_logs_by_date_range_from_crud(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )


def get_all_krs_by_cycle_from_crud(
    *,
    crud_module,
    cycle_id: int,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[KeyResult]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_all_krs_by_cycle(
            int(cycle_id),
            limit=limit,
            offset=int(offset),
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_all_krs_by_cycle",
                result=backend_result,
            )
            or []
        )
    return crud_data_helpers.get_all_krs_by_cycle_from_crud(
        cycle_id=cycle_id,
        limit=limit,
        offset=offset,
    )


def get_all_tasks_by_cycle_from_crud(
    *,
    crud_module,
    cycle_id: int,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Task]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_all_tasks_by_cycle(
            int(cycle_id),
            limit=limit,
            offset=int(offset),
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_all_tasks_by_cycle",
                result=backend_result,
            )
            or []
        )
    return crud_data_helpers.get_all_tasks_by_cycle_from_crud(
        cycle_id=cycle_id,
        limit=limit,
        offset=offset,
    )


def get_active_weekly_plan_from_crud(
    *,
    crud_module,
    user_id: int,
    date: Optional[datetime] = None,
) -> Optional[WeeklyPlan]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_active_weekly_plan(
            int(user_id),
            date=date,
            actor_username=actor,
        )
        return backend_read_result_or_raise_from_crud(
            crud_module=crud_module,
            operation="get_active_weekly_plan",
            result=backend_result,
        )
    return crud_reflection_helpers.get_active_weekly_plan_from_crud(
        crud_module=crud_module,
        user_id=user_id,
        date=date,
    )


def get_user_retrospectives_from_crud(
    *,
    crud_module,
    user_id: int,
    cycle_id: Optional[int] = None,
) -> List[Retrospective]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_user_retrospectives(
            user_id=int(user_id),
            cycle_id=int(cycle_id) if cycle_id is not None else None,
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_user_retrospectives",
                result=backend_result,
            )
            or []
        )
    return crud_reflection_helpers.get_user_retrospectives_from_crud(
        crud_module=crud_module,
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_team_retrospectives_from_crud(
    *,
    crud_module,
    manager_id: int,
    cycle_id: Optional[int] = None,
) -> List[Retrospective]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_team_retrospectives(
            manager_id=int(manager_id),
            cycle_id=int(cycle_id) if cycle_id is not None else None,
            actor_username=actor,
        )
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_team_retrospectives",
                result=backend_result,
            )
            or []
        )
    return crud_reflection_helpers.get_team_retrospectives_from_crud(
        crud_module=crud_module,
        manager_id=manager_id,
        cycle_id=cycle_id,
    )


def get_all_teams_from_crud(*, crud_module) -> List[Team]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_all_teams(actor_username=actor)
        return list(
            backend_read_result_or_raise_from_crud(
                crud_module=crud_module,
                operation="get_all_teams",
                result=backend_result,
            )
            or []
        )
    return crud_team_helpers.get_all_teams_from_crud(
        crud_module=crud_module,
    )


def get_team_by_id_from_crud(
    *,
    crud_module,
    team_id: int,
) -> Optional[Team]:
    if backend_read_proxy_enabled_from_crud(crud_module=crud_module):
        from src.services import backend_client

        actor = resolve_backend_actor_from_crud(crud_module=crud_module)
        backend_result = backend_client.read_team_by_id(
            int(team_id),
            actor_username=actor,
        )
        return backend_read_result_or_raise_from_crud(
            crud_module=crud_module,
            operation="get_team_by_id",
            result=backend_result,
        )
    return crud_team_helpers.get_team_by_id_from_crud(
        crud_module=crud_module,
        team_id=team_id,
    )


def get_node_by_external_id_from_crud(*, crud_module, external_id: str):
    return crud_query_helpers.get_node_by_external_id_from_crud(
        crud_module=crud_module,
        external_id=external_id,
    )


def get_user_data_from_sql_from_crud(
    *,
    crud_module,
    username: str,
    cycle_id: Optional[int] = None,
    goal_limit: Optional[int] = None,
    goal_offset: int = 0,
    include_work_logs: bool = True,
) -> dict:
    return crud_data_helpers.get_user_data_from_sql_from_crud(
        crud_module=crud_module,
        username=username,
        cycle_id=cycle_id,
        goal_limit=goal_limit,
        goal_offset=goal_offset,
        include_work_logs=include_work_logs,
    )


def get_sql_id_by_external_from_crud(
    *, crud_module, external_id: str, model_class
) -> Optional[int]:
    return crud_data_helpers.get_sql_id_by_external_from_crud(
        crud_module=crud_module,
        external_id=external_id,
        model_class=model_class,
    )
