"""Inspector helper routines for AI analysis and mutations."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import session_keys


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
    if node_type_upper != "KEY_RESULT":
        return

    st_module.markdown("---")
    st_module.markdown("### AI Strategic Analysis")
    if st_module.button("Run Analysis", type="primary", key=f"run_ai_insp_{node_id}"):
        with st_module.spinner("Analyzing..."):
            result = analyze_node_fn(node_id, "KEY_RESULT", actor_username=username)
            if "error" not in result:
                update_key_result_fn(
                    node_id,
                    gemini_analysis=result,
                    actor_username=username,
                )
                rerun_fn()

    analysis_raw = getattr(node, "gemini_analysis", None)
    if not analysis_raw:
        return

    analysis_data = None
    if isinstance(analysis_raw, str):
        try:
            parsed = json_loads_fn(analysis_raw)
            analysis_data = parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            if logger is not None:
                logger.debug(
                    "Failed to parse KR analysis JSON for node %s: %s", node_id, exc
                )
            try:
                fallback = literal_eval_fn(analysis_raw)
                if isinstance(fallback, dict):
                    analysis_data = fallback
                    update_key_result_fn(
                        node_id,
                        gemini_analysis=analysis_data,
                        actor_username=username,
                    )
            except Exception as nested_exc:
                if logger is not None:
                    logger.debug(
                        "Failed to normalize KR analysis payload for node %s: %s",
                        node_id,
                        nested_exc,
                    )
                analysis_data = None
    elif isinstance(analysis_raw, dict):
        analysis_data = analysis_raw

    if not analysis_data:
        st_module.code(str(analysis_raw))
        return

    c_m1, c_m2, c_m3 = st_module.columns(3)
    if analysis_data.get("efficiency_score") is not None:
        c_m1.metric("Efficiency", f"{analysis_data.get('efficiency_score')}%")
    if analysis_data.get("effectiveness_score") is not None:
        c_m2.metric("Effectiveness", f"{analysis_data.get('effectiveness_score')}%")
    if analysis_data.get("overall_score") is not None:
        c_m3.metric("Overall", f"{analysis_data.get('overall_score')}%")

    if analysis_data.get("summary"):
        st_module.info(analysis_data["summary"])

    for warning_item in analysis_data.get("deadline_warnings") or []:
        st_module.warning(warning_item)

    gap_analysis = analysis_data.get("gap_analysis")
    quality_assessment = analysis_data.get("quality_assessment")
    if gap_analysis or quality_assessment:
        c_g, c_q = st_module.columns(2)
        if gap_analysis:
            c_g.markdown("**Gap Analysis**")
            c_g.write(gap_analysis)
        if quality_assessment:
            c_q.markdown("**Quality Assessment**")
            c_q.write(quality_assessment)

    proposed_tasks = analysis_data.get("proposed_tasks") or []
    if proposed_tasks:
        st_module.markdown("**Proposed Tasks**")
        for item in proposed_tasks:
            st_module.markdown(f"- {item}")


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
    """Render inspector delete action and cleanup.

    Returns True when caller should abort due to an error.
    """
    st_module.markdown("---")
    can_delete = bool(username)
    if not can_delete:
        return False

    if st_module.button("Delete Entity", type="primary", key=f"del_insp_{node_id}"):
        try:
            if node_type_upper == "GOAL":
                delete_goal_fn(node_id, actor_username=username)
            elif node_type_upper == "OBJECTIVE":
                delete_objective_fn(node_id, actor_username=username)
            elif node_type_upper == "KEY_RESULT":
                delete_key_result_fn(node_id, actor_username=username)
            elif node_type_upper == "TASK":
                delete_task_fn(node_id, actor_username=username)
        except PermissionError as exc:
            st_module.error(str(exc))
            return True

        keys_to_clear = [
            key
            for key in session_state.keys()
            if str(key).startswith(session_keys.OKR_DATA_CACHE_PREFIX)
        ]
        for key in keys_to_clear:
            del session_state[key]

        if session_keys.NAV_STACK in session_state:
            nav_stack = session_state.get(session_keys.NAV_STACK) or []
            session_state[session_keys.NAV_STACK] = [
                item for item in nav_stack if not str(item).endswith(str(node_id))
            ]

        if session_keys.ACTIVE_INSPECTOR_ID in session_state:
            del session_state[session_keys.ACTIVE_INSPECTOR_ID]

        rerun_fn()

    return False


def handle_save_changes(
    *,
    st_module: Any,
    can_save: bool,
    node_type_upper: str,
    node_id: int,
    username: str,
    new_title: str,
    new_description: str,
    new_progress: int,
    new_cycle_id: Any,
    new_strat_tags_input: str,
    new_score_mode: Any,
    new_obj_weight: float,
    new_state: Any,
    new_reflection: str,
    new_start: float,
    new_target: float,
    new_current: float,
    new_unit: str,
    new_metric_type: Any,
    new_weight: float,
    new_init_tags_input: str,
    new_assignee_id: Any,
    update_goal_fn: Callable[..., Any],
    update_objective_fn: Callable[..., Any],
    update_key_result_fn: Callable[..., Any],
    update_task_fn: Callable[..., Any],
    submit_button_fn: Callable[..., bool] | None = None,
    rerun_fn: Callable[[], Any],
) -> bool:
    """Handle inspector Save Changes dispatch by node type.

    Returns True when caller should abort due to an error.
    """
    if submit_button_fn is None:
        submit_button_fn = getattr(st_module, "form_submit_button")

    if not submit_button_fn("Save Changes", disabled=not can_save):
        return False

    updates: dict[str, Any] = {
        "title": new_title,
        "description": new_description,
        "progress": new_progress,
    }

    try:
        if node_type_upper == "GOAL":
            updates.update(
                {
                    "cycle_id": new_cycle_id,
                    "strategy_tags": [
                        item.strip()
                        for item in str(new_strat_tags_input or "").split(",")
                        if item.strip()
                    ],
                }
            )
            update_goal_fn(node_id, actor_username=username, **updates)
        elif node_type_upper == "OBJECTIVE":
            updates.update(
                {
                    "score_mode": new_score_mode,
                    "weight": new_obj_weight,
                    "state": new_state,
                    "final_reflection": new_reflection,
                }
            )
            update_objective_fn(node_id, actor_username=username, **updates)
        elif node_type_upper == "KEY_RESULT":
            updates.update(
                {
                    "start_value": new_start,
                    "target_value": new_target,
                    "current_value": new_current,
                    "unit": new_unit,
                    "metric_type": new_metric_type,
                    "weight": new_weight,
                    "state": new_state,
                    "final_reflection": new_reflection,
                    "initiative_tags": [
                        item.strip()
                        for item in str(new_init_tags_input or "").split(",")
                        if item.strip()
                    ],
                }
            )
            update_key_result_fn(node_id, actor_username=username, **updates)
        elif node_type_upper == "TASK":
            updates.update({"assignee_id": new_assignee_id})
            update_task_fn(node_id, actor_username=username, **updates)
    except PermissionError as exc:
        st_module.error(str(exc))
        return True

    st_module.success("Saved!")
    rerun_fn()
    return False
