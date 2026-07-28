"""Read/query facade wrappers for `src.crud`."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from src.domain import read_service
from src.models import (
    CheckIn,
    Cycle,
    DashboardGoal,
    Experiment,
    Goal,
    KeyResult,
    Retrospective,
    Team,
    Task,
    User,
    WeeklyPlan,
)


def _crud_module():
    import sys

    return sys.modules.get("src.crud", sys.modules[__name__])


def get_all_users() -> List[User]:
    """Get all users."""
    return read_service.get_all_users_from_crud(crud_module=_crud_module())


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by id."""
    return read_service.get_user_by_id_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
    )


def get_team_members(manager_id: int) -> List[User]:
    """Get all users managed by a specific manager."""
    return read_service.get_team_members_from_crud(
        crud_module=_crud_module(),
        manager_id=manager_id,
    )


def get_check_ins(kr_id: int) -> List[CheckIn]:
    """Get all check-ins for a KR, ordered by date desc."""
    return read_service.get_check_ins_from_crud(
        crud_module=_crud_module(),
        kr_id=kr_id,
    )


def get_krs_needing_checkin(
    user_id: str, cycle_id: int, days_threshold: int = 7
) -> List[KeyResult]:
    return read_service.get_krs_needing_checkin_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        cycle_id=cycle_id,
        days_threshold=days_threshold,
    )


def list_experiments_for_kr(
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    """List all experiments for a KR. Enforces goal-scoped read access."""
    return read_service.list_experiments_for_kr_from_crud(
        crud_module=_crud_module(),
        key_result_id=key_result_id,
        actor_username=actor_username,
    )


def get_active_experiments_for_kr(
    key_result_id: int,
    actor_username: str,
) -> List[Experiment]:
    """Get RUNNING experiments for a KR. Enforces goal-scoped read access."""
    return read_service.get_active_experiments_for_kr_from_crud(
        crud_module=_crud_module(),
        key_result_id=key_result_id,
        actor_username=actor_username,
    )


def list_experiments_for_retro_window(
    cycle_id: int,
    window_start: datetime,
    window_end: datetime,
    actor_username: str,
) -> List[Experiment]:
    """
    List experiments for retro review within a week window.
    Returns experiments that ended in the window OR are still running.
    Enforces goal-scoped access per experiment.
    """
    return read_service.list_experiments_for_retro_window_from_crud(
        crud_module=_crud_module(),
        cycle_id=cycle_id,
        window_start=window_start,
        window_end=window_end,
        actor_username=actor_username,
    )


def get_active_cycles() -> List[Cycle]:
    """Get all active cycles."""
    return read_service.get_active_cycles_from_crud(crud_module=_crud_module())


def get_all_cycles() -> List[Cycle]:
    """Get all cycles."""
    return read_service.get_all_cycles_from_crud(crud_module=_crud_module())


def get_dashboard_data(
    user_id: str, cycle_id: Optional[int] = None
) -> List[DashboardGoal]:
    """
    Get lightweight goal data for dashboard display.
    Uses JOINs to count strategies and objectives without loading full tree.
    """
    return read_service.get_dashboard_data_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_goal_tree(goal_id: int) -> Optional[Goal]:
    """
    Load complete hierarchy for a goal with all nested relationships.
    Uses eager loading for efficiency.
    """
    return read_service.get_goal_tree_from_crud(
        crud_module=_crud_module(),
        goal_id=goal_id,
    )


def get_user_goals_simple(user_id: str, cycle_id: Optional[int] = None) -> List[Goal]:
    """Get all goals for a user (without full tree)."""
    return read_service.get_user_goals_simple_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_node(node_id: int, node_type: str, actor_username: Optional[str] = None):
    """Fetch a node by ID and Type string (GOAL, OBJECTIVE, KEY_RESULT, TASK)."""
    return read_service.get_node_from_crud(
        crud_module=_crud_module(),
        node_id=node_id,
        node_type=node_type,
        actor_username=actor_username,
    )


def get_node_by_external_id(external_id: str):
    """Search all OKR tables for a node with the given external_id (UUID)."""
    return read_service.get_node_by_external_id_from_crud(
        crud_module=_crud_module(),
        external_id=external_id,
    )


def get_leadership_metrics(usernames: List[str], cycle_id: int):
    """Aggregate portfolio-level metrics for leadership dashboards."""
    return read_service.get_leadership_metrics_from_crud(
        crud_module=_crud_module(),
        usernames=usernames,
        cycle_id=cycle_id,
    )


def get_work_logs_by_date_range(
    user_id: int, start_date: datetime, end_date: datetime
) -> List:
    return read_service.get_work_logs_by_date_range_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )


def get_all_krs_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[KeyResult]:
    """Paged KR read for cycle-level analytics/report rendering."""
    return read_service.get_all_krs_by_cycle_from_crud(
        crud_module=_crud_module(),
        cycle_id=cycle_id,
        limit=limit,
        offset=offset,
    )


def get_all_tasks_by_cycle(
    cycle_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Task]:
    """Paged task read for cycle scans with optional query limits."""
    return read_service.get_all_tasks_by_cycle_from_crud(
        crud_module=_crud_module(),
        cycle_id=cycle_id,
        limit=limit,
        offset=offset,
    )


def get_hours_by_goal(user_id: int, days: int = 7) -> dict:
    return read_service.get_hours_by_goal_from_crud(
        user_id=user_id,
        days=days,
    )


def get_daily_work_trend(user_id: int, days: int = 7) -> dict:
    return read_service.get_daily_work_trend_from_crud(
        user_id=user_id,
        days=days,
    )


def get_active_weekly_plan(
    user_id: int, date: Optional[datetime] = None
) -> Optional[WeeklyPlan]:
    """Get the weekly plan active for the given date (default: now)."""
    return read_service.get_active_weekly_plan_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        date=date,
    )


def get_user_retrospectives(
    user_id: int, cycle_id: Optional[int] = None
) -> List[Retrospective]:
    """Get all retrospectives for a user."""
    return read_service.get_user_retrospectives_from_crud(
        crud_module=_crud_module(),
        user_id=user_id,
        cycle_id=cycle_id,
    )


def get_team_retrospectives(
    manager_id: int, cycle_id: Optional[int] = None
) -> List[Retrospective]:
    """Get retrospectives for all members of a manager's team."""
    return read_service.get_team_retrospectives_from_crud(
        crud_module=_crud_module(),
        manager_id=manager_id,
        cycle_id=cycle_id,
    )


def get_user_data_from_sql(
    username: str,
    cycle_id: Optional[int] = None,
    *,
    goal_limit: Optional[int] = None,
    goal_offset: int = 0,
    include_work_logs: bool = True,
) -> dict:
    """
    Reconstructs the hierarchical JSON-like dictionary structure from the SQL database.
    This allows the UI to continue using its existing logic while powered by SQL.
    """
    return read_service.get_user_data_from_sql_from_crud(
        crud_module=_crud_module(),
        username=username,
        cycle_id=cycle_id,
        goal_limit=goal_limit,
        goal_offset=goal_offset,
        include_work_logs=include_work_logs,
    )


def get_sql_id_by_external(external_id: str, model_class) -> Optional[int]:
    """Helper to get SQL internal ID from JSON external UUID/ID."""
    return read_service.get_sql_id_by_external_from_crud(
        crud_module=_crud_module(),
        external_id=external_id,
        model_class=model_class,
    )


def get_all_teams() -> List[Team]:
    """Retrieve all teams."""
    return read_service.get_all_teams_from_crud(crud_module=_crud_module())


def get_team_by_id(team_id: int) -> Optional[Team]:
    """Retrieve a team by ID."""
    return read_service.get_team_by_id_from_crud(
        crud_module=_crud_module(),
        team_id=team_id,
    )
