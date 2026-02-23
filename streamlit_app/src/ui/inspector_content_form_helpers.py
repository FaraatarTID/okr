"""Inspector content helpers for edit-form rendering and save dispatch."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from src.ui import inspector_alignment_helpers
from src.ui import inspector_form_helpers


@dataclass(frozen=True)
class InspectorEditFormDeps:
    cached_get_all_users_fn: Callable[[], list[Any]]
    cached_get_user_by_id_fn: Callable[[Any], Any]
    cached_get_team_members_fn: Callable[[Any], list[Any]]
    score_mode_enum: Any
    metric_type_enum: Any
    lifecycle_state_enum: Any
    calculate_kr_score_fn: Callable[..., float]
    calculate_objective_score_fn: Callable[..., float]
    get_score_label_fn: Callable[[float], str]
    get_score_color_band_fn: Callable[[float], str]
    get_allowed_transitions_fn: Callable[[Any], list[Any]]
    state_icons: dict[Any, str]
    state_hints: dict[Any, str]
    get_all_cycles_fn: Callable[[], list[Any]]
    get_session_context_fn: Callable[..., Any]
    get_alignment_neighbors_fn: Callable[..., Any]
    create_alignment_fn: Callable[..., Any]
    delete_alignment_fn: Callable[..., Any]
    update_goal_fn: Callable[..., Any]
    update_objective_fn: Callable[..., Any]
    update_key_result_fn: Callable[..., Any]
    update_task_fn: Callable[..., Any]
    rerun_fn: Callable[[], Any]


@dataclass(frozen=True)
class InspectorEditFormContext:
    st_module: Any
    node: Any
    node_id: int
    title: str
    progress: int
    node_type_upper: str
    has_children: bool
    username: str
    logger: Any
    deps: InspectorEditFormDeps


def render_inspector_edit_form_with_context(context: InspectorEditFormContext) -> bool:
    """Render the inspector edit form and dispatch save operations.

    Returns True when caller should abort due to permission errors.
    """
    deps = context.deps
    with context.st_module.form(key=f"edit_form_{context.node_id}"):
        new_title = context.st_module.text_input("Title", value=context.title)
        new_description = context.st_module.text_area(
            "Description", value=getattr(context.node, "description", "") or ""
        )
        new_assignee_id = inspector_form_helpers.resolve_task_assignee(
            st_module=context.st_module,
            session_state=context.st_module.session_state,
            node=context.node,
            node_type_upper=context.node_type_upper,
            node_id=context.node_id,
            get_all_users_fn=deps.cached_get_all_users_fn,
            get_user_by_id_fn=deps.cached_get_user_by_id_fn,
            get_team_members_fn=deps.cached_get_team_members_fn,
        )

        col1, col2 = context.st_module.columns(2)
        with col1:
            progress_container = context.st_module.empty()
            if context.has_children:
                progress_container.metric(
                    "Progress (Calculated)", value=f"{context.progress}%"
                )
                new_progress = int(context.progress)
            else:
                new_progress = int(
                    progress_container.slider(
                        "Progress (Manual)", 0, 100, value=int(context.progress)
                    )
                )

        with col2:
            context.st_module.text_input(
                "Type",
                value=context.node_type_upper.replace("_", " ").title(),
                disabled=True,
                key=f"type_disp_{context.node_id}",
            )

        new_score_mode, new_obj_weight = (
            inspector_form_helpers.resolve_objective_scoring_section(
                st_module=context.st_module,
                node=context.node,
                node_type_upper=context.node_type_upper,
                node_id=context.node_id,
                score_mode_enum=deps.score_mode_enum,
                calculate_kr_score_fn=deps.calculate_kr_score_fn,
                get_score_label_fn=deps.get_score_label_fn,
                get_score_color_band_fn=deps.get_score_color_band_fn,
                calculate_objective_score_fn=deps.calculate_objective_score_fn,
            )
        )

        new_cycle_id, new_strat_tags_input = (
            inspector_form_helpers.resolve_goal_cycle_and_strategy_tags(
                st_module=context.st_module,
                node=context.node,
                node_type_upper=context.node_type_upper,
                node_id=context.node_id,
                get_all_cycles_fn=deps.get_all_cycles_fn,
                json_loads_fn=json.loads,
                logger=context.logger,
            )
        )

        kr_metrics = inspector_form_helpers.resolve_key_result_metrics_section(
            st_module=context.st_module,
            node=context.node,
            node_type_upper=context.node_type_upper,
            node_id=context.node_id,
            has_children=context.has_children,
            new_progress_value=int(new_progress),
            metric_type_enum=deps.metric_type_enum,
            calculate_kr_score_fn=deps.calculate_kr_score_fn,
            get_score_label_fn=deps.get_score_label_fn,
            get_score_color_band_fn=deps.get_score_color_band_fn,
            json_loads_fn=json.loads,
            logger=context.logger,
        )
        new_start = float(kr_metrics.get("new_start", 0.0) or 0.0)
        new_target = float(kr_metrics.get("new_target", 100.0) or 100.0)
        new_current = float(kr_metrics.get("new_current", 0.0) or 0.0)
        new_unit = str(kr_metrics.get("new_unit", "%") or "%")
        new_init_tags_input = str(kr_metrics.get("new_init_tags_input", "") or "")
        new_weight = float(kr_metrics.get("new_weight", 1.0) or 1.0)
        new_metric_type = kr_metrics.get(
            "new_metric_type", deps.metric_type_enum.NUMERIC
        )
        new_progress = int(kr_metrics.get("new_progress", new_progress) or new_progress)

        new_state, new_reflection = inspector_form_helpers.resolve_lifecycle_section(
            st_module=context.st_module,
            node=context.node,
            node_type_upper=context.node_type_upper,
            node_id=context.node_id,
            lifecycle_state_enum=deps.lifecycle_state_enum,
            get_allowed_transitions_fn=deps.get_allowed_transitions_fn,
            state_icons=deps.state_icons,
            state_hints=deps.state_hints,
        )

        inspector_alignment_helpers.render_objective_alignment_section(
            st_module=context.st_module,
            node_type_upper=context.node_type_upper,
            node_id=context.node_id,
            username=context.username,
            get_session_context_fn=deps.get_session_context_fn,
            get_alignment_neighbors_fn=deps.get_alignment_neighbors_fn,
            create_alignment_fn=deps.create_alignment_fn,
            delete_alignment_fn=deps.delete_alignment_fn,
            rerun_fn=deps.rerun_fn,
        )

        should_abort_save = inspector_form_helpers.handle_save_changes(
            st_module=context.st_module,
            can_save=bool(context.username),
            node_type_upper=context.node_type_upper,
            node_id=context.node_id,
            username=context.username,
            new_title=new_title,
            new_description=new_description,
            new_progress=int(new_progress),
            new_cycle_id=new_cycle_id,
            new_strat_tags_input=new_strat_tags_input,
            new_score_mode=new_score_mode,
            new_obj_weight=float(new_obj_weight),
            new_state=new_state,
            new_reflection=new_reflection,
            new_start=float(new_start),
            new_target=float(new_target),
            new_current=float(new_current),
            new_unit=new_unit,
            new_metric_type=new_metric_type,
            new_weight=float(new_weight),
            new_init_tags_input=new_init_tags_input,
            new_assignee_id=new_assignee_id,
            update_goal_fn=deps.update_goal_fn,
            update_objective_fn=deps.update_objective_fn,
            update_key_result_fn=deps.update_key_result_fn,
            update_task_fn=deps.update_task_fn,
            submit_button_fn=context.st_module.form_submit_button,
            rerun_fn=deps.rerun_fn,
        )

    return bool(should_abort_save)


def render_inspector_edit_form(
    *,
    st_module: Any,
    node: Any,
    node_id: int,
    title: str,
    progress: int,
    node_type_upper: str,
    has_children: bool,
    username: str,
    logger: Any,
    cached_get_all_users_fn: Callable[[], list[Any]],
    cached_get_user_by_id_fn: Callable[[Any], Any],
    cached_get_team_members_fn: Callable[[Any], list[Any]],
    score_mode_enum: Any,
    metric_type_enum: Any,
    lifecycle_state_enum: Any,
    calculate_kr_score_fn: Callable[..., float],
    calculate_objective_score_fn: Callable[..., float],
    get_score_label_fn: Callable[[float], str],
    get_score_color_band_fn: Callable[[float], str],
    get_allowed_transitions_fn: Callable[[Any], list[Any]],
    state_icons: dict[Any, str],
    state_hints: dict[Any, str],
    get_all_cycles_fn: Callable[[], list[Any]],
    get_session_context_fn: Callable[..., Any],
    get_alignment_neighbors_fn: Callable[..., Any],
    create_alignment_fn: Callable[..., Any],
    delete_alignment_fn: Callable[..., Any],
    update_goal_fn: Callable[..., Any],
    update_objective_fn: Callable[..., Any],
    update_key_result_fn: Callable[..., Any],
    update_task_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
) -> bool:
    """Backward-compatible wrapper for existing call sites/tests."""
    deps = InspectorEditFormDeps(
        cached_get_all_users_fn=cached_get_all_users_fn,
        cached_get_user_by_id_fn=cached_get_user_by_id_fn,
        cached_get_team_members_fn=cached_get_team_members_fn,
        score_mode_enum=score_mode_enum,
        metric_type_enum=metric_type_enum,
        lifecycle_state_enum=lifecycle_state_enum,
        calculate_kr_score_fn=calculate_kr_score_fn,
        calculate_objective_score_fn=calculate_objective_score_fn,
        get_score_label_fn=get_score_label_fn,
        get_score_color_band_fn=get_score_color_band_fn,
        get_allowed_transitions_fn=get_allowed_transitions_fn,
        state_icons=state_icons,
        state_hints=state_hints,
        get_all_cycles_fn=get_all_cycles_fn,
        get_session_context_fn=get_session_context_fn,
        get_alignment_neighbors_fn=get_alignment_neighbors_fn,
        create_alignment_fn=create_alignment_fn,
        delete_alignment_fn=delete_alignment_fn,
        update_goal_fn=update_goal_fn,
        update_objective_fn=update_objective_fn,
        update_key_result_fn=update_key_result_fn,
        update_task_fn=update_task_fn,
        rerun_fn=rerun_fn,
    )
    context = InspectorEditFormContext(
        st_module=st_module,
        node=node,
        node_id=node_id,
        title=title,
        progress=progress,
        node_type_upper=node_type_upper,
        has_children=has_children,
        username=username,
        logger=logger,
        deps=deps,
    )
    return render_inspector_edit_form_with_context(context)
