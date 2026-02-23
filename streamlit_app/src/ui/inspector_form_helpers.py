"""Inspector form helper routines."""

from __future__ import annotations

from typing import Any, Callable


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
    current_assignee_id = (
        getattr(node, "assignee_id", None) if node_type_upper == "TASK" else None
    )
    if node_type_upper != "TASK":
        return current_assignee_id

    user_role = session_state.get("user_role")
    if user_role in ["admin", "manager"]:
        potential_assignees: list[Any] = []
        if user_role == "admin":
            potential_assignees = list(get_all_users_fn() or [])
        elif user_role == "manager":
            manager_id = session_state.get("user_id")
            manager_obj = get_user_by_id_fn(manager_id)
            potential_assignees = list(get_team_members_fn(manager_id) or [])
            if manager_obj:
                potential_assignees.append(manager_obj)

        assignee_ids: list[int] = []
        assignee_labels: dict[int, str] = {}
        for user_option in potential_assignees:
            user_id = getattr(user_option, "id", None)
            if user_id is None:
                continue
            user_id = int(user_id)
            assignee_ids.append(user_id)
            display_name = (
                getattr(user_option, "display_name", None)
                or getattr(user_option, "username", None)
                or f"user_{user_id}"
            )
            username = getattr(user_option, "username", None) or f"user_{user_id}"
            assignee_labels[user_id] = f"{display_name} (@{username}) | #{user_id}"

        if assignee_ids:
            curr_idx_ass = 0
            if current_assignee_id:
                try:
                    curr_idx_ass = assignee_ids.index(int(current_assignee_id))
                except ValueError:
                    curr_idx_ass = 0

            selected_assignee_id = st_module.selectbox(
                "Assign To",
                options=assignee_ids,
                index=curr_idx_ass,
                format_func=lambda uid: assignee_labels.get(uid, f"User #{uid}"),
                key=f"assign_sel_{node_id}",
            )
            return int(selected_assignee_id)
        return current_assignee_id

    assignee_obj = getattr(node, "assignee", None)
    if assignee_obj:
        display_name = (
            getattr(assignee_obj, "display_name", None)
            or getattr(assignee_obj, "username", None)
            or "Unknown"
        )
        st_module.info(f"👥 **Assigned To:** {display_name}")
    else:
        st_module.info("👥 **Unassigned**")
    return current_assignee_id


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
    new_score_mode = getattr(node, "score_mode", score_mode_enum.UNWEIGHTED)
    new_obj_weight = float(getattr(node, "weight", 1.0) or 1.0)
    if node_type_upper != "OBJECTIVE":
        return new_score_mode, new_obj_weight

    st_module.markdown("---")
    st_module.caption("Objective Scoring & Weight")
    oc1, oc2 = st_module.columns(2)
    new_obj_weight = float(
        oc1.number_input(
            "Weight",
            value=float(new_obj_weight),
            min_value=0.0,
            step=0.1,
            key=f"obj_weight_{node_id}",
        )
    )

    mode_options = [mode.value for mode in score_mode_enum]
    curr_mode = getattr(node, "score_mode", score_mode_enum.UNWEIGHTED)
    curr_mode_value = getattr(curr_mode, "value", str(curr_mode))
    try:
        curr_mode_index = mode_options.index(curr_mode_value)
    except ValueError:
        curr_mode_index = 0
    new_mode_val = oc2.selectbox(
        "Score Mode",
        options=mode_options,
        index=curr_mode_index,
        key=f"score_mode_{node_id}",
    )
    new_score_mode = score_mode_enum(new_mode_val)

    key_results = list(getattr(node, "key_results", []) or [])
    if not key_results:
        return new_score_mode, new_obj_weight

    kr_scores: list[float] = []
    kr_weights: list[float] = []
    for kr in key_results:
        score = float(
            calculate_kr_score_fn(
                current=getattr(kr, "current_value", None),
                target=getattr(kr, "target_value", None),
                start=getattr(kr, "start_value", None),
                metric_type=getattr(kr, "metric_type", None),
            )
        )
        kr_scores.append(score)
        kr_weights.append(float(getattr(kr, "weight", 1.0) or 1.0))

    weighted = new_score_mode == score_mode_enum.WEIGHTED
    objective_score = float(
        calculate_objective_score_fn(
            kr_scores,
            kr_weights if weighted else None,
            weighted=weighted,
        )
    )
    score_label = get_score_label_fn(objective_score)
    band_class = get_score_color_band_fn(objective_score)
    st_module.markdown(
        f"**Current Score:** <span class='atlas-attn-chip {band_class}'>{objective_score:.2f} ({score_label})</span>",
        unsafe_allow_html=True,
    )
    return new_score_mode, new_obj_weight


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
    new_cycle_id = getattr(node, "cycle_id", None)
    new_strat_tags_input = ""
    if node_type_upper != "GOAL":
        return new_cycle_id, new_strat_tags_input

    st_module.markdown("---")
    st_module.caption("Cycle Assignment")
    all_cycles = list(get_all_cycles_fn() or [])
    cycle_titles = [str(getattr(cycle, "title", "")) for cycle in all_cycles]
    cycle_ids = [getattr(cycle, "id", None) for cycle in all_cycles]

    if cycle_titles:
        try:
            curr_idx_cyc = cycle_ids.index(new_cycle_id)
        except Exception as exc:
            if logger is not None:
                logger.debug(
                    "Failed to resolve current cycle index for node %s: %s",
                    node_id,
                    exc,
                )
            curr_idx_cyc = 0

        sel_cyc = st_module.selectbox(
            "Assign to Cycle",
            options=cycle_titles,
            index=curr_idx_cyc,
            key=f"cyc_assign_{node_id}",
        )
        if sel_cyc in cycle_titles:
            new_cycle_id = all_cycles[cycle_titles.index(sel_cyc)].id
    else:
        st_module.info("No cycles available.")

    st_module.caption("Strategy Tags")
    raw_strats = getattr(node, "strategy_tags", "[]")
    curr_strats: list[str] = []
    if isinstance(raw_strats, str):
        try:
            parsed = json_loads_fn(raw_strats)
            if isinstance(parsed, list):
                curr_strats = [str(item) for item in parsed]
            else:
                curr_strats = []
        except Exception as exc:
            if logger is not None:
                logger.debug(
                    "Failed to parse strategy_tags JSON for node %s: %s",
                    node_id,
                    exc,
                )
            curr_strats = [
                item.strip() for item in raw_strats.split(",") if item.strip()
            ]
    elif isinstance(raw_strats, list):
        curr_strats = [str(item) for item in raw_strats]

    default_tags_value = ", ".join(
        [item.strip() for item in curr_strats if item.strip()]
    )
    new_strat_tags_input = st_module.text_input(
        "Add Strategy Tags (comma-separated)",
        value=default_tags_value,
        key=f"strat_tags_{node_id}",
    )
    return new_cycle_id, str(new_strat_tags_input)


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
    values = {
        "new_start": float(getattr(node, "start_value", 0.0) or 0.0),
        "new_target": float(getattr(node, "target_value", 100.0) or 100.0),
        "new_current": float(getattr(node, "current_value", 0.0) or 0.0),
        "new_unit": str(getattr(node, "unit", "%") or "%"),
        "new_init_tags_input": "",
        "new_weight": float(getattr(node, "weight", 1.0) or 1.0),
        "new_metric_type": getattr(node, "metric_type", metric_type_enum.NUMERIC),
        "new_progress": int(new_progress_value),
    }
    if node_type_upper != "KEY_RESULT":
        return values

    st_module.markdown("---")
    st_module.caption("Progress Metrics")
    mc0_in, mc1_in, mc2_in, mc3_in = st_module.columns(4)
    values["new_start"] = float(
        mc0_in.number_input(
            "Start Value",
            value=float(values["new_start"]),
            key=f"start_{node_id}",
        )
    )
    values["new_target"] = float(
        mc1_in.number_input(
            "Target Value",
            value=float(values["new_target"]),
            key=f"target_{node_id}",
        )
    )
    values["new_current"] = float(
        mc2_in.number_input(
            "Current Value",
            value=float(values["new_current"]),
            key=f"curr_val_{node_id}",
        )
    )
    values["new_unit"] = str(
        mc3_in.text_input(
            "Unit",
            value=str(values["new_unit"]),
            key=f"unit_{node_id}",
        )
    )

    curr_score = float(
        calculate_kr_score_fn(
            current=values["new_current"],
            target=values["new_target"],
            start=values["new_start"],
            metric_type=getattr(node, "metric_type", metric_type_enum.NUMERIC),
        )
    )
    score_label = get_score_label_fn(curr_score)
    band_class = get_score_color_band_fn(curr_score)
    st_module.markdown(
        f"**Current Score:** <span class='atlas-attn-chip {band_class}'>{curr_score:.2f} ({score_label})</span>",
        unsafe_allow_html=True,
    )

    if values["new_target"] > 0:
        calc_p = int((values["new_current"] / values["new_target"]) * 100)
        calc_p = max(0, min(100, calc_p))
        if not has_children:
            values["new_progress"] = calc_p
            st_module.info(f"Calculated Progress: {calc_p}%")

    st_module.caption("Initiative Tags")
    raw_inits = getattr(node, "initiative_tags", "[]")
    curr_inits: list[str] = []
    if isinstance(raw_inits, str):
        try:
            parsed = json_loads_fn(raw_inits)
            if isinstance(parsed, list):
                curr_inits = [str(item) for item in parsed]
            else:
                curr_inits = []
        except Exception as exc:
            if logger is not None:
                logger.debug(
                    "Failed to parse initiative_tags JSON for node %s: %s",
                    node_id,
                    exc,
                )
            curr_inits = [item.strip() for item in raw_inits.split(",") if item.strip()]
    elif isinstance(raw_inits, list):
        curr_inits = [str(item) for item in raw_inits]
    default_init_tags = ", ".join([item.strip() for item in curr_inits if item.strip()])
    values["new_init_tags_input"] = str(
        st_module.text_input(
            "Add Initiative Tags (comma-separated)",
            value=default_init_tags,
            key=f"init_tags_{node_id}",
        )
    )

    st_module.markdown("---")
    st_module.caption("KR Weight & Metric Type")
    w_col1, w_col2 = st_module.columns(2)
    values["new_weight"] = float(
        w_col1.number_input(
            "Weight",
            value=float(values["new_weight"]),
            min_value=0.0,
            step=0.1,
            key=f"weight_{node_id}",
        )
    )
    metric_type_options = [item.value for item in metric_type_enum]
    curr_metric_type = getattr(node, "metric_type", metric_type_enum.NUMERIC)
    curr_metric_type_value = getattr(curr_metric_type, "value", str(curr_metric_type))
    try:
        metric_type_index = metric_type_options.index(curr_metric_type_value)
    except ValueError:
        metric_type_index = 0
    new_metric_type_val = w_col2.selectbox(
        "Metric Type",
        options=metric_type_options,
        index=metric_type_index,
        key=f"metric_type_{node_id}",
    )
    values["new_metric_type"] = metric_type_enum(new_metric_type_val)

    return values


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
    current_state = getattr(node, "state", lifecycle_state_enum.DRAFT)
    try:
        current_state = lifecycle_state_enum(current_state)
    except Exception:
        current_state = lifecycle_state_enum.DRAFT

    new_state = current_state
    new_reflection = str(getattr(node, "final_reflection", "") or "")

    if node_type_upper not in ["OBJECTIVE", "KEY_RESULT"]:
        return new_state, new_reflection

    st_module.markdown("---")
    st_module.caption("Lifecycle & Closing")
    s_col1, _s_col2 = st_module.columns(2)

    allowed_next = list(get_allowed_transitions_fn(current_state) or [])
    options = [current_state] + [
        state for state in allowed_next if state != current_state
    ]
    state_value_options = [state.value for state in options]
    label_map = {
        state.value: f"{state_icons.get(state, '')} {state.value.title()}"
        for state in options
    }

    new_state_val = s_col1.selectbox(
        "Lifecycle State",
        options=state_value_options,
        format_func=lambda value: label_map.get(value, value),
        index=0,
        key=f"state_sel_{node_id}",
        help="Transition rules are enforced. Draft -> Active -> Grading -> Archived.",
    )
    new_state = lifecycle_state_enum(new_state_val)

    st_module.info(f"**{new_state.value.title()}**: {state_hints.get(new_state, '')}")
    if node_type_upper == "OBJECTIVE" and new_state != current_state:
        st_module.warning(
            f"Changing this Objective to **{new_state.value.title()}** will also update all its Key Results."
        )

    new_reflection = str(
        st_module.text_area(
            "Final Reflection",
            value=new_reflection,
            placeholder="What did we learn? Why did we (or didn't we) achieve this?",
            key=f"reflection_{node_id}",
        )
        or ""
    )
    return new_state, new_reflection


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
    """Render task scheduling/deadline controls.

    Returns True when caller should abort due to an error.
    """
    if node_type_upper != "TASK":
        return False

    st_module.markdown("---")
    st_module.write("### Schedule")

    curr_sd = (
        node.start_date.date()
        if isinstance(getattr(node, "start_date", None), datetime_cls)
        else None
    )
    curr_d = (
        node.deadline.date()
        if isinstance(getattr(node, "deadline", None), datetime_cls)
        else None
    )

    col_sch1, col_sch2 = st_module.columns(2)
    with col_sch1:
        new_sd = st_module.date_input(
            "Start Date", value=curr_sd, key=f"sd_inp_{node_id}"
        )
        if st_module.button("Save Start Date", key=f"save_sd_{node_id}"):
            new_sd_dt = (
                datetime_cls.combine(new_sd, datetime_cls.min.time())
                if new_sd
                else None
            )
            try:
                update_task_fn(node_id, start_date=new_sd_dt, actor_username=username)
            except PermissionError as exc:
                st_module.error(str(exc))
                return True
            rerun_fn()

    with col_sch2:
        new_d = st_module.date_input("Due Date", value=curr_d, key=f"dl_inp_{node_id}")
        if st_module.button("Save Due Date", key=f"save_dl_{node_id}"):
            new_dl_dt = (
                datetime_cls.combine(new_d, datetime_cls.max.time()) if new_d else None
            )
            try:
                update_task_fn(node_id, deadline=new_dl_dt, actor_username=username)
            except PermissionError as exc:
                st_module.error(str(exc))
                return True
            rerun_fn()

    clr1, clr2 = st_module.columns(2)
    if curr_sd and clr1.button("Clear Start", key=f"clear_sd_{node_id}"):
        try:
            update_task_fn(node_id, start_date=None, actor_username=username)
        except PermissionError as exc:
            st_module.error(str(exc))
            return True
        rerun_fn()

    has_deadline = getattr(node, "deadline", None) is not None
    if has_deadline and clr2.button("Clear Due", key=f"clear_dl_{node_id}"):
        try:
            update_task_fn(node_id, deadline=None, actor_username=username)
        except PermissionError as exc:
            st_module.error(str(exc))
            return True
        rerun_fn()

    if has_deadline:
        try:
            _status_code, status_label, health = get_deadline_status_fn(node)
            st_module.metric("Deadline Status", status_label)
            st_module.progress(float(health) / 100.0)
        except Exception as exc:
            if logger is not None:
                logger.debug(
                    "Failed to compute inspector deadline status for node %s: %s",
                    node_id,
                    exc,
                )

    return False


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
    """Render task work-history list and delete actions.

    Returns True when caller should abort due to an error.
    """
    if node_type_upper != "TASK":
        st_module.markdown("---")
        st_module.info(
            "Work logs are attached to tasks. Select a task in Focus Map to view its Work History."
        )
        return False

    st_module.markdown("---")
    st_module.markdown("### Work History")
    work_logs = list(get_work_logs_fn(getattr(node, "id", None)) or [])
    st_module.caption(f"Work logs found: {len(work_logs)}")

    if not work_logs:
        st_module.info("No work logs found for this task.")
        if st_module.button("Refresh Work History"):
            rerun_fn()
        return False

    sorted_logs = sorted(
        work_logs,
        key=lambda item: getattr(item, "end_time", None) or datetime_cls.min,
        reverse=True,
    )
    for log_item in sorted_logs:
        end_time_value = getattr(log_item, "end_time", None)
        ended_at = (
            end_time_value.strftime("%Y-%m-%d %H:%M") if end_time_value else "Running"
        )
        duration_minutes = round(
            float(getattr(log_item, "duration_minutes", 0) or 0), 1
        )
        summary_text = getattr(log_item, "summary", None) or "-"

        col_l1, col_l2 = st_module.columns([0.9, 0.1])
        col_l1.write(f"**{ended_at}** | {duration_minutes}m | {summary_text}")
        if col_l2.button("Delete", key=f"del_log_{getattr(log_item, 'id', '')}"):
            try:
                delete_work_log_fn(
                    getattr(log_item, "id", None),
                    actor_username=username,
                )
            except PermissionError as exc:
                st_module.error(str(exc))
                return True
            rerun_fn()

    return False


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
            if str(key).startswith("okr_data_cache_")
        ]
        for key in keys_to_clear:
            del session_state[key]

        if "nav_stack" in session_state:
            nav_stack = session_state.get("nav_stack") or []
            session_state["nav_stack"] = [
                item for item in nav_stack if not str(item).endswith(str(node_id))
            ]

        if "active_inspector_id" in session_state:
            del session_state["active_inspector_id"]

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
