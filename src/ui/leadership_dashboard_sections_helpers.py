"""Compatibility wrappers for leadership dashboard section helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import leadership_dashboard_chart_helpers
from src.ui import leadership_dashboard_coach_helpers
from src.ui import leadership_dashboard_filter_helpers


def render_refresh_controls(*, st_module: Any) -> None:
    leadership_dashboard_filter_helpers.render_refresh_controls(st_module=st_module)


def resolve_selected_members(
    *,
    st_module: Any,
    username: str,
    user_role: str,
    cached_get_all_users_fn: Callable[[], list[Any]],
    cached_get_team_members_fn: Callable[[Any], list[Any]],
    get_user_by_id_fn: Callable[[Any], Any],
) -> tuple[list[str], dict[str, str], bool]:
    return leadership_dashboard_filter_helpers.resolve_selected_members(
        st_module=st_module,
        username=username,
        user_role=user_role,
        cached_get_all_users_fn=cached_get_all_users_fn,
        cached_get_team_members_fn=cached_get_team_members_fn,
        get_user_by_id_fn=get_user_by_id_fn,
    )


def render_scorecard_metrics(
    *,
    st_module: Any,
    metrics: dict[str, Any],
    member_deadline_data: list[dict[str, Any]],
) -> dict[str, int]:
    return leadership_dashboard_chart_helpers.render_scorecard_metrics(
        st_module=st_module,
        metrics=metrics,
        member_deadline_data=member_deadline_data,
    )


def render_progress_by_member_chart(
    *,
    st_module: Any,
    selected_members: list[str],
    member_progress_data: list[dict[str, Any]],
) -> None:
    leadership_dashboard_chart_helpers.render_progress_by_member_chart(
        st_module=st_module,
        selected_members=selected_members,
        member_progress_data=member_progress_data,
    )


def render_deadline_health_chart(
    *,
    st_module: Any,
    selected_members: list[str],
    member_deadline_data: list[dict[str, Any]],
) -> None:
    leadership_dashboard_chart_helpers.render_deadline_health_chart(
        st_module=st_module,
        selected_members=selected_members,
        member_deadline_data=member_deadline_data,
    )


def render_strategic_alignment_matrix(
    *,
    st_module: Any,
    heatmap_data: list[dict[str, Any]],
) -> None:
    leadership_dashboard_chart_helpers.render_strategic_alignment_matrix(
        st_module=st_module,
        heatmap_data=heatmap_data,
    )


def render_at_risk_key_results(
    *,
    st_module: Any,
    at_risk_items: list[dict[str, Any]],
) -> None:
    leadership_dashboard_chart_helpers.render_at_risk_key_results(
        st_module=st_module,
        at_risk_items=at_risk_items,
    )


def build_overdue_tasks(
    *,
    cycle_id: Any,
    cached_get_all_tasks_by_cycle_fn: Callable[..., list[Any]],
    cycle_task_scan_limit_fn: Callable[[], int],
    utc_now_naive_fn: Callable[[], Any],
    get_deadline_status_fn: Callable[[Any], tuple[Any, str, Any]],
    users_map: dict[Any, Any],
    logger: Any,
) -> tuple[list[dict[str, Any]], int, int]:
    return leadership_dashboard_filter_helpers.build_overdue_tasks(
        cycle_id=cycle_id,
        cached_get_all_tasks_by_cycle_fn=cached_get_all_tasks_by_cycle_fn,
        cycle_task_scan_limit_fn=cycle_task_scan_limit_fn,
        utc_now_naive_fn=utc_now_naive_fn,
        get_deadline_status_fn=get_deadline_status_fn,
        users_map=users_map,
        logger=logger,
    )


def render_overdue_tasks(
    *,
    st_module: Any,
    overdue_tasks: list[dict[str, Any]],
    scanned_task_count: int,
    task_scan_limit: int,
) -> None:
    leadership_dashboard_chart_helpers.render_overdue_tasks(
        st_module=st_module,
        overdue_tasks=overdue_tasks,
        scanned_task_count=scanned_task_count,
        task_scan_limit=task_scan_limit,
    )


def render_ai_team_coach(
    *,
    st_module: Any,
    user_role: str,
    member_progress_data: list[dict[str, Any]],
    aggregate_deadline: dict[str, int],
    metrics: dict[str, Any],
    analyze_team_health_fn: Callable[[dict[str, Any]], dict[str, Any]],
    escape_html_fn: Callable[[str], str],
    logger: Any,
) -> None:
    leadership_dashboard_coach_helpers.render_ai_team_coach(
        st_module=st_module,
        user_role=user_role,
        member_progress_data=member_progress_data,
        aggregate_deadline=aggregate_deadline,
        metrics=metrics,
        analyze_team_health_fn=analyze_team_health_fn,
        escape_html_fn=escape_html_fn,
        logger=logger,
    )
