"""Inspector content rendering helper."""

from __future__ import annotations

import json
from datetime import datetime

from src.crud import get_session_context
from src.domain.lifecycle import get_allowed_transitions, STATE_HINTS, STATE_ICONS
from src.domain.scoring import calculate_kr_score, get_score_color_band, get_score_label
from src.models import ScoreMode, MetricType, LifecycleState
from src.ui import inspector_alignment_helpers
from src.ui import inspector_form_helpers
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
        delete_goal,
        delete_objective,
        delete_key_result,
        delete_task,
        delete_work_log,
        get_all_cycles,
    )
    from src.models import Goal, Objective, KeyResult, Task, WorkLog

    inspector_shell_helpers.inject_dialog_css(st_module=st_module)

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

    # Extract properties from SQLModel object
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

    with st_module.form(key=f"edit_form_{node_id}"):
        new_title_insp = st_module.text_input("Title", value=title_insp)
        new_desc_insp = st_module.text_area("Description", value=node.description or "")
        new_assignee_id_insp = inspector_form_helpers.resolve_task_assignee(
            st_module=st_module,
            session_state=st_module.session_state,
            node=node,
            node_type_upper=node_type_insp,
            node_id=node_id,
            get_all_users_fn=cached_get_all_users_fn,
            get_user_by_id_fn=cached_get_user_by_id_fn,
            get_team_members_fn=cached_get_team_members_fn,
        )

        col1_insp, col2_insp = st_module.columns(2)
        with col1_insp:
            p_prog_cont = st_module.empty()
            if has_children_insp:
                p_prog_cont.metric("Progress (Calculated)", value=f"{progress_insp}%")
                new_progress_insp = progress_insp
            else:
                new_progress_insp = p_prog_cont.slider(
                    "Progress (Manual)", 0, 100, value=progress_insp
                )

        with col2_insp:
            # Type is now READ-ONLY in Inspector to maintain hierarchy integrity
            st_module.text_input(
                "Type",
                value=node_type_insp.replace("_", " ").title(),
                disabled=True,
                key=f"type_disp_{node_id}",
            )
            new_type_insp = node_type_insp

        # OBJECTIVE Specific Score Mode and Weight
        from src.domain.scoring import calculate_objective_score

        new_score_mode, new_obj_weight_insp = (
            inspector_form_helpers.resolve_objective_scoring_section(
                st_module=st_module,
                node=node,
                node_type_upper=node_type_insp,
                node_id=node_id,
                score_mode_enum=ScoreMode,
                calculate_kr_score_fn=calculate_kr_score,
                get_score_label_fn=get_score_label,
                get_score_color_band_fn=get_score_color_band,
                calculate_objective_score_fn=calculate_objective_score,
            )
        )

        # GOAL Specific Cycle Assignment and Tags
        new_cycle_id_insp, new_strat_tags_input = (
            inspector_form_helpers.resolve_goal_cycle_and_strategy_tags(
                st_module=st_module,
                node=node,
                node_type_upper=node_type_insp,
                node_id=node_id,
                get_all_cycles_fn=get_all_cycles,
                json_loads_fn=json.loads,
                logger=logger,
            )
        )

        # KEY_RESULT Specific Metrics
        kr_metrics = inspector_form_helpers.resolve_key_result_metrics_section(
            st_module=st_module,
            node=node,
            node_type_upper=node_type_insp,
            node_id=node_id,
            has_children=has_children_insp,
            new_progress_value=int(new_progress_insp),
            metric_type_enum=MetricType,
            calculate_kr_score_fn=calculate_kr_score,
            get_score_label_fn=get_score_label,
            get_score_color_band_fn=get_score_color_band,
            json_loads_fn=json.loads,
            logger=logger,
        )
        new_start_insp = float(kr_metrics.get("new_start", 0.0) or 0.0)
        new_target_insp = float(kr_metrics.get("new_target", 100.0) or 100.0)
        new_curr_insp = float(kr_metrics.get("new_current", 0.0) or 0.0)
        new_unit_insp = str(kr_metrics.get("new_unit", "%") or "%")
        new_init_tags_input = str(kr_metrics.get("new_init_tags_input", "") or "")
        new_weight_insp = float(kr_metrics.get("new_weight", 1.0) or 1.0)
        new_metric_type = kr_metrics.get("new_metric_type", MetricType.NUMERIC)
        new_progress_insp = int(kr_metrics.get("new_progress", new_progress_insp) or new_progress_insp)

        # Phase 2: Lifecycle State & Reflection
        new_state, new_reflection = inspector_form_helpers.resolve_lifecycle_section(
            st_module=st_module,
            node=node,
            node_type_upper=node_type_insp,
            node_id=node_id,
            lifecycle_state_enum=LifecycleState,
            get_allowed_transitions_fn=get_allowed_transitions,
            state_icons=STATE_ICONS,
            state_hints=STATE_HINTS,
        )

        # Phase 3: Alignment Graph (Vertical/Horizontal Links)
        from src.domain.alignment import get_alignment_neighbors
        from src.crud import create_alignment, delete_alignment

        inspector_alignment_helpers.render_objective_alignment_section(
            st_module=st_module,
            node_type_upper=node_type_insp,
            node_id=node_id,
            username=username,
            get_session_context_fn=get_session_context,
            get_alignment_neighbors_fn=get_alignment_neighbors,
            create_alignment_fn=create_alignment,
            delete_alignment_fn=delete_alignment,
            rerun_fn=st_module.rerun,
        )

        can_save_insp = bool(username)

        should_abort_save = inspector_form_helpers.handle_save_changes(
            st_module=st_module,
            can_save=can_save_insp,
            node_type_upper=node_type_insp,
            node_id=node_id,
            username=username,
            new_title=new_title_insp,
            new_description=new_desc_insp,
            new_progress=int(new_progress_insp),
            new_cycle_id=new_cycle_id_insp,
            new_strat_tags_input=new_strat_tags_input,
            new_score_mode=new_score_mode,
            new_obj_weight=float(new_obj_weight_insp),
            new_state=new_state,
            new_reflection=new_reflection,
            new_start=float(new_start_insp),
            new_target=float(new_target_insp),
            new_current=float(new_curr_insp),
            new_unit=new_unit_insp,
            new_metric_type=new_metric_type,
            new_weight=float(new_weight_insp),
            new_init_tags_input=new_init_tags_input,
            new_assignee_id=new_assignee_id_insp,
            update_goal_fn=update_goal,
            update_objective_fn=update_objective,
            update_key_result_fn=update_key_result,
            update_task_fn=update_task,
            rerun_fn=st_module.rerun,
        )
        if should_abort_save:
            return
    from src.utils.deadline_utils import get_deadline_status

    should_abort_task_schedule = inspector_form_helpers.render_task_schedule_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_insp,
        node_id=node_id,
        username=username,
        update_task_fn=update_task,
        datetime_cls=datetime,
        get_deadline_status_fn=get_deadline_status,
        rerun_fn=st_module.rerun,
        logger=logger,
    )
    if should_abort_task_schedule:
        return

    from src.crud import delete_work_log

    should_abort_task_history = inspector_form_helpers.render_task_work_history_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_insp,
        username=username,
        get_work_logs_fn=cached_get_work_logs_fn,
        delete_work_log_fn=delete_work_log,
        rerun_fn=st_module.rerun,
        datetime_cls=datetime,
    )
    if should_abort_task_history:
        return

    from src.crud import update_key_result
    from src.services.ai_service import analyze_node
    import ast

    inspector_form_helpers.render_key_result_ai_analysis_section(
        st_module=st_module,
        node=node,
        node_type_upper=node_type_insp,
        node_id=node_id,
        username=username,
        analyze_node_fn=analyze_node,
        update_key_result_fn=update_key_result,
        json_loads_fn=json.loads,
        literal_eval_fn=ast.literal_eval,
        rerun_fn=st_module.rerun,
        logger=logger,
    )

    from src.crud import (
        delete_goal,
        delete_key_result,
        delete_objective,
        delete_task,
    )

    should_abort_delete = inspector_form_helpers.render_delete_entity_section(
        st_module=st_module,
        session_state=st_module.session_state,
        node_type_upper=node_type_insp,
        node_id=node_id,
        username=username,
        delete_goal_fn=delete_goal,
        delete_objective_fn=delete_objective,
        delete_key_result_fn=delete_key_result,
        delete_task_fn=delete_task,
        rerun_fn=st_module.rerun,
    )
    if should_abort_delete:
        return

