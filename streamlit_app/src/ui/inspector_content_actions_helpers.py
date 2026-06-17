"""Inspector content helpers for post-form task/AI/delete sections."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
import ast
import json

from src.ui import inspector_form_helpers


def render_inspector_post_form_sections(
    *,
    st_module: Any,
    node: Any,
    node_id: int,
    node_type_upper: str,
    username: str,
    logger: Any,
    cached_get_work_logs_fn: Callable[[Any], list[Any]],
    get_deadline_status_fn: Callable[[Any], tuple[Any, str, Any]],
    analyze_node_fn: Callable[..., dict[str, Any]],
    update_task_fn: Callable[..., Any],
    update_key_result_fn: Callable[..., Any],
    delete_goal_fn: Callable[..., Any],
    delete_objective_fn: Callable[..., Any],
    delete_key_result_fn: Callable[..., Any],
    delete_task_fn: Callable[..., Any],
    delete_work_log_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
) -> bool:
    """Render sections that follow the edit form.

    Returns True when caller should abort due to permission errors.
    """
    should_abort_task_schedule = inspector_form_helpers.render_task_schedule_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        username=username,
        update_task_fn=update_task_fn,
        datetime_cls=datetime,
        get_deadline_status_fn=get_deadline_status_fn,
        rerun_fn=rerun_fn,
        logger=logger,
    )
    if should_abort_task_schedule:
        return True

    should_abort_task_history = inspector_form_helpers.render_task_work_history_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        username=username,
        get_work_logs_fn=cached_get_work_logs_fn,
        delete_work_log_fn=delete_work_log_fn,
        rerun_fn=rerun_fn,
        datetime_cls=datetime,
    )
    if should_abort_task_history:
        return True

    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_upper,
        node_id=node_id,
        username=username,
        analyze_node_fn=analyze_node_fn,
        update_key_result_fn=update_key_result_fn,
        json_loads_fn=json.loads,
        literal_eval_fn=ast.literal_eval,
        rerun_fn=rerun_fn,
        logger=logger,
    )

    should_abort_delete = inspector_form_helpers.render_delete_entity_section(
        st_module=st_module,
        session_state=st_module.session_state,
        node_type_upper=node_type_upper,
        node_id=node_id,
        username=username,
        delete_goal_fn=delete_goal_fn,
        delete_objective_fn=delete_objective_fn,
        delete_key_result_fn=delete_key_result_fn,
        delete_task_fn=delete_task_fn,
        rerun_fn=rerun_fn,
    )
    if should_abort_delete:
        return True

    return False
