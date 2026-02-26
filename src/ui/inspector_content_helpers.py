"""Inspector content rendering helper."""

from __future__ import annotations

from src.domain.lifecycle import get_allowed_transitions, STATE_HINTS, STATE_ICONS
from src.domain.scoring import (
    calculate_kr_score,
    calculate_objective_score,
    get_score_color_band,
    get_score_label,
)
from src.models import ScoreMode, MetricType, LifecycleState
from src.ui import inspector_content_actions_helpers
from src.ui import inspector_content_form_helpers
from src.ui import inspector_shell_helpers


def render_inspector_content(
    node_id,
    node_type,
    username,
    show_close=True,
    *,
    st_module,
    cached_get_node_fn,
    cached_get_all_users_fn,
    cached_get_user_by_id_fn,
    cached_get_team_members_fn,
    cached_get_work_logs_fn,
    type_icons,
    logger,
):
    """
    Refactored Inspector. Uses SQLModel objects directly via crud.py.
    node_type: GOAL, OBJECTIVE, KEY_RESULT, or TASK
    """
    from src.crud import (
        update_goal,
        update_objective,
        update_key_result,
        update_task,
        create_alignment,
        delete_alignment,
        delete_goal,
        delete_objective,
        delete_key_result,
        delete_task,
        delete_work_log,
        get_all_cycles,
    )
    from src.services.ai_service import analyze_node
    from src.utils.deadline_utils import get_deadline_status

    inspector_shell_helpers.inject_dialog_css(st_module=st_module)

    def _disabled_session_context():
        raise RuntimeError(
            "Direct frontend DB sessions are disabled in backend-segregated mode."
        )

    # Fetch node (cached to prevent rerun DB bottleneck)
    node = cached_get_node_fn(node_id, node_type, actor_username=username)
    if not node:
        if inspector_shell_helpers.handle_missing_node(
            st_module=st_module,
            session_state=st_module.session_state,
            node_id=node_id,
            node_type=node_type,
            rerun_fn=st_module.rerun,
        ):
            return

    node_context = inspector_shell_helpers.derive_node_context(
        node=node,
        node_type=node_type,
    )
    title_insp = node_context["title"]
    progress_insp = node_context["progress"]
    node_type_insp = node_context["node_type_upper"]
    has_children_insp = bool(node_context["has_children"])

    inspector_shell_helpers.render_header(
        st_module=st_module,
        session_state=st_module.session_state,
        show_close=show_close,
        node_id=node_id,
        node_type_upper=node_type_insp,
        title=title_insp,
        type_icons=type_icons,
        rerun_fn=st_module.rerun,
    )

    edit_form_deps = inspector_content_form_helpers.InspectorEditFormDeps(
        cached_get_all_users_fn=cached_get_all_users_fn,
        cached_get_user_by_id_fn=cached_get_user_by_id_fn,
        cached_get_team_members_fn=cached_get_team_members_fn,
        score_mode_enum=ScoreMode,
        metric_type_enum=MetricType,
        lifecycle_state_enum=LifecycleState,
        calculate_kr_score_fn=calculate_kr_score,
        calculate_objective_score_fn=calculate_objective_score,
        get_score_label_fn=get_score_label,
        get_score_color_band_fn=get_score_color_band,
        get_allowed_transitions_fn=get_allowed_transitions,
        state_icons=STATE_ICONS,
        state_hints=STATE_HINTS,
        get_all_cycles_fn=get_all_cycles,
        get_session_context_fn=_disabled_session_context,
        get_alignment_neighbors_fn=(lambda *_args, **_kwargs: ([], [])),
        create_alignment_fn=create_alignment,
        delete_alignment_fn=delete_alignment,
        update_goal_fn=update_goal,
        update_objective_fn=update_objective,
        update_key_result_fn=update_key_result,
        update_task_fn=update_task,
        rerun_fn=st_module.rerun,
    )
    edit_form_context = inspector_content_form_helpers.InspectorEditFormContext(
        st_module=st_module,
        node=node,
        node_id=node_id,
        title=title_insp,
        progress=int(progress_insp),
        node_type_upper=node_type_insp,
        has_children=has_children_insp,
        username=username,
        logger=logger,
        deps=edit_form_deps,
    )
    if inspector_content_form_helpers.render_inspector_edit_form_with_context(
        edit_form_context
    ):
        return

    if inspector_content_actions_helpers.render_inspector_post_form_sections(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_insp,
        node_id=node_id,
        username=username,
        logger=logger,
        cached_get_work_logs_fn=(
            lambda task_id: cached_get_work_logs_fn(
                task_id,
                actor_username=username,
            )
        ),
        get_deadline_status_fn=get_deadline_status,
        analyze_node_fn=analyze_node,
        update_task_fn=update_task,
        update_key_result_fn=update_key_result,
        delete_goal_fn=delete_goal,
        delete_objective_fn=delete_objective,
        delete_key_result_fn=delete_key_result,
        delete_task_fn=delete_task,
        delete_work_log_fn=delete_work_log,
        rerun_fn=st_module.rerun,
    ):
        return
