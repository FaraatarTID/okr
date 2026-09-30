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


def get_krs_needing_checkin_from_crud(
    *,
    crud_module,
    user_id: str,
    cycle_id: int,
    days_threshold: int = 7,
) -> List[KeyResult]:
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
    return crud_auth_helpers.get_all_users_from_crud(crud_module=crud_module)


def get_team_members_from_crud(*, crud_module, manager_id: int) -> List[User]:
    return crud_auth_helpers.get_team_members_from_crud(
        crud_module=crud_module,
        manager_id=manager_id,
    )


def get_user_goals_from_crud(*, crud_module, username: str, cycle_id: int):
    return crud_auth_helpers.get_user_goals_from_crud(
        crud_module=crud_module,
        username=username,
        cycle_id=cycle_id,
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
    return crud_experiment_helpers.list_experiments_for_retro_window_from_crud(
        crud_module=crud_module,
        cycle_id=cycle_id,
        window_start=window_start,
        window_end=window_end,
        actor_username=actor_username,
    )


def get_active_cycles_from_crud(*, crud_module) -> List[Cycle]:
    return crud_cycle_helpers.get_active_cycles_from_crud(
        crud_module=crud_module,
    )


def get_all_cycles_from_crud(*, crud_module) -> List[Cycle]:
    return crud_cycle_helpers.get_all_cycles_from_crud(
        crud_module=crud_module,
    )


def get_node_from_crud(
    *,
    crud_module,
    node_id: int,
    node_type: str,
    actor_username: Optional[str] = None,
    allow_unscoped: bool = False,
):
    return crud_query_helpers.get_node_from_crud(
        crud_module=crud_module,
        node_id=node_id,
        node_type=node_type,
        actor_username=actor_username,
        allow_unscoped=allow_unscoped,
    )


def get_leadership_metrics_from_crud(
    *,
    crud_module,
    usernames,
    cycle_id: int,
):
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
    return crud_reflection_helpers.get_team_retrospectives_from_crud(
        crud_module=crud_module,
        manager_id=manager_id,
        cycle_id=cycle_id,
    )


def get_all_teams_from_crud(*, crud_module) -> List[Team]:
    return crud_team_helpers.get_all_teams_from_crud(
        crud_module=crud_module,
    )


def get_team_by_id_from_crud(
    *,
    crud_module,
    team_id: int,
) -> Optional[Team]:
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
