"""Leadership dashboard rendering helpers."""

from __future__ import annotations

from src.ui import leadership_dashboard_sections_helpers


def render_leadership_dashboard_content(
    username,
    *,
    st_module,
    cached_get_all_users_fn,
    cached_get_team_members_fn,
    cached_get_leadership_metrics_fn,
    cached_get_all_tasks_by_cycle_fn,
    cycle_task_scan_limit_fn,
    utc_now_naive_fn,
    escape_html_fn,
    logger,
):
    """Render leadership dashboard content."""
    cycle_id = st_module.session_state.get("active_cycle_id")
    if not cycle_id:
        st_module.warning("Please select a cycle to view insights.")
        return

    leadership_dashboard_sections_helpers.render_refresh_controls(st_module=st_module)

    user_role = st_module.session_state.get("user_role", "member")
    from src.crud import get_user_by_id

    selected_members, _member_display_map, should_abort_filter = (
        leadership_dashboard_sections_helpers.resolve_selected_members(
            st_module=st_module,
            username=username,
            user_role=str(user_role),
            cached_get_all_users_fn=cached_get_all_users_fn,
            cached_get_team_members_fn=cached_get_team_members_fn,
            get_user_by_id_fn=get_user_by_id,
        )
    )
    if should_abort_filter:
        return

    from src.utils.deadline_utils import get_deadline_status

    metrics = cached_get_leadership_metrics_fn(
        selected_members,
        cycle_id,
        actor_username=username,
    )
    if not metrics:
        st_module.error("Could not fetch metrics.")
        return
    users_map = {u.id: u for u in cached_get_all_users_fn() if u.id is not None}

    member_progress_data = metrics.get("member_progress", [])
    member_deadline_data = metrics.get("member_deadlines", [])

    aggregate_deadline = leadership_dashboard_sections_helpers.render_scorecard_metrics(
        st_module=st_module,
        metrics=metrics,
        member_deadline_data=member_deadline_data,
    )

    leadership_dashboard_sections_helpers.render_progress_by_member_chart(
        st_module=st_module,
        selected_members=selected_members,
        member_progress_data=member_progress_data,
    )
    leadership_dashboard_sections_helpers.render_deadline_health_chart(
        st_module=st_module,
        selected_members=selected_members,
        member_deadline_data=member_deadline_data,
    )
    leadership_dashboard_sections_helpers.render_strategic_alignment_matrix(
        st_module=st_module,
        heatmap_data=list(metrics.get("heatmap_data", []) or []),
    )
    leadership_dashboard_sections_helpers.render_at_risk_key_results(
        st_module=st_module,
        at_risk_items=list(metrics.get("at_risk", []) or []),
    )

    overdue_tasks, scanned_task_count, task_scan_limit = (
        leadership_dashboard_sections_helpers.build_overdue_tasks(
            cycle_id=cycle_id,
            cached_get_all_tasks_by_cycle_fn=cached_get_all_tasks_by_cycle_fn,
            cycle_task_scan_limit_fn=cycle_task_scan_limit_fn,
            utc_now_naive_fn=utc_now_naive_fn,
            get_deadline_status_fn=get_deadline_status,
            users_map=users_map,
            logger=logger,
        )
    )
    leadership_dashboard_sections_helpers.render_overdue_tasks(
        st_module=st_module,
        overdue_tasks=overdue_tasks,
        scanned_task_count=scanned_task_count,
        task_scan_limit=task_scan_limit,
    )

    from src.services.ai_service import analyze_team_health

    leadership_dashboard_sections_helpers.render_ai_team_coach(
        st_module=st_module,
        user_role=str(user_role),
        member_progress_data=member_progress_data,
        aggregate_deadline=aggregate_deadline,
        metrics=metrics,
        analyze_team_health_fn=analyze_team_health,
        escape_html_fn=escape_html_fn,
        logger=logger,
    )
