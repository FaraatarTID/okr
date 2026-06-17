"""Inspector form helper routines."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import inspector_mutation_helpers
from src.ui import inspector_resolution_helpers
from src.ui import inspector_state_helpers
from src.ui import inspector_task_form_helpers


def resolve_task_assignee(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    node: Any,
    node_type_upper: str,
    node_id: int,
    get_all_users_fn: Callable[[], list[Any]],
    get_user_by_id_fn: Callable[[Any], Any],
    get_team_members_fn: Callable[[Any], list[Any]],
) -> Any:
    return inspector_state_helpers.resolve_task_assignee(
        st_module=st_module,
        session_state=session_state,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        get_all_users_fn=get_all_users_fn,
        get_user_by_id_fn=get_user_by_id_fn,
        get_team_members_fn=get_team_members_fn,
    )


def resolve_objective_scoring_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    score_mode_enum: Any,
    calculate_kr_score_fn: Callable[..., float],
    get_score_label_fn: Callable[[float], str],
    get_score_color_band_fn: Callable[[float], str],
    calculate_objective_score_fn: Callable[..., float],
) -> tuple[Any, float]:
    return inspector_resolution_helpers.resolve_objective_scoring_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        score_mode_enum=score_mode_enum,
        calculate_kr_score_fn=calculate_kr_score_fn,
        get_score_label_fn=get_score_label_fn,
        get_score_color_band_fn=get_score_color_band_fn,
        calculate_objective_score_fn=calculate_objective_score_fn,
    )


def resolve_goal_cycle_and_strategy_tags(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    get_all_cycles_fn: Callable[[], list[Any]],
    json_loads_fn: Callable[[str], Any],
    logger: Any,
) -> tuple[Any, str]:
    return inspector_resolution_helpers.resolve_goal_cycle_and_strategy_tags(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        get_all_cycles_fn=get_all_cycles_fn,
        json_loads_fn=json_loads_fn,
        logger=logger,
    )


def resolve_key_result_metrics_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    has_children: bool,
    new_progress_value: int,
    metric_type_enum: Any,
    calculate_kr_score_fn: Callable[..., float],
    get_score_label_fn: Callable[[float], str],
    get_score_color_band_fn: Callable[[float], str],
    json_loads_fn: Callable[[str], Any],
    logger: Any,
) -> dict[str, Any]:
    return inspector_resolution_helpers.resolve_key_result_metrics_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        has_children=has_children,
        new_progress_value=new_progress_value,
        metric_type_enum=metric_type_enum,
        calculate_kr_score_fn=calculate_kr_score_fn,
        get_score_label_fn=get_score_label_fn,
        get_score_color_band_fn=get_score_color_band_fn,
        json_loads_fn=json_loads_fn,
        logger=logger,
    )


def resolve_lifecycle_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    lifecycle_state_enum: Any,
    get_allowed_transitions_fn: Callable[[Any], list[Any]],
    state_icons: dict[Any, str],
    state_hints: dict[Any, str],
) -> tuple[Any, str]:
    return inspector_state_helpers.resolve_lifecycle_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        lifecycle_state_enum=lifecycle_state_enum,
        get_allowed_transitions_fn=get_allowed_transitions_fn,
        state_icons=state_icons,
        state_hints=state_hints,
    )


def render_task_schedule_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    username: str,
    update_task_fn: Callable[..., Any],
    datetime_cls: Any,
    get_deadline_status_fn: Callable[[Any], tuple[Any, str, Any]],
    rerun_fn: Callable[[], Any],
    logger: Any,
) -> bool:
    """Render task scheduling/deadline controls."""
    return inspector_task_form_helpers.render_task_schedule_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        username=username,
        update_task_fn=update_task_fn,
        datetime_cls=datetime_cls,
        get_deadline_status_fn=get_deadline_status_fn,
        rerun_fn=rerun_fn,
        logger=logger,
    )


def render_task_work_history_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    username: str,
    get_work_logs_fn: Callable[[Any], list[Any]],
    delete_work_log_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
    datetime_cls: Any,
) -> bool:
    """Render task work-history list and delete actions."""
    return inspector_task_form_helpers.render_task_work_history_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        username=username,
        get_work_logs_fn=get_work_logs_fn,
        delete_work_log_fn=delete_work_log_fn,
        rerun_fn=rerun_fn,
        datetime_cls=datetime_cls,
    )


def render_key_result_ai_analysis_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    username: str,
    analyze_node_fn: Callable[..., dict[str, Any]],
    update_key_result_fn: Callable[..., Any],
    json_loads_fn: Callable[[str], Any],
    literal_eval_fn: Callable[[str], Any],
    rerun_fn: Callable[[], Any],
    logger: Any,
) -> None:
    inspector_mutation_helpers.render_key_result_ai_analysis_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        username=username,
        analyze_node_fn=analyze_node_fn,
        update_key_result_fn=update_key_result_fn,
        json_loads_fn=json_loads_fn,
        literal_eval_fn=literal_eval_fn,
        rerun_fn=rerun_fn,
        logger=logger,
    )


def render_delete_entity_section(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    node_type_upper: str,
    node_id: int,
    username: str,
    delete_goal_fn: Callable[..., Any],
    delete_objective_fn: Callable[..., Any],
    delete_key_result_fn: Callable[..., Any],
    delete_task_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
) -> bool:
    """Render inspector delete action and cleanup."""
    return inspector_mutation_helpers.render_delete_entity_section(
        st_module=st_module,
        session_state=session_state,
        node_type_upper=node_type_upper,
        node_id=node_id,
        username=username,
        delete_goal_fn=delete_goal_fn,
        delete_objective_fn=delete_objective_fn,
        delete_key_result_fn=delete_key_result_fn,
        delete_task_fn=delete_task_fn,
        rerun_fn=rerun_fn,
    )


handle_save_changes = inspector_mutation_helpers.handle_save_changes
