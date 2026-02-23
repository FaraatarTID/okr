"""Inspector helper routines for resolving node-specific form inputs."""

from __future__ import annotations

from typing import Any, Callable


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
    """Resolve objective-level score mode/weight inputs and preview score."""
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


def _parse_tag_values(
    *,
    raw_value: Any,
    node_id: int,
    logger: Any,
    json_loads_fn: Callable[[str], Any],
    logger_message: str,
) -> list[str]:
    """Normalize JSON/csv/list tag payloads to a plain list of strings."""
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value]

    if isinstance(raw_value, str):
        try:
            parsed = json_loads_fn(raw_value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
            return []
        except Exception as exc:
            if logger is not None:
                logger.debug(logger_message, node_id, exc)
            return [item.strip() for item in raw_value.split(",") if item.strip()]

    return []


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
    """Resolve goal cycle assignment and strategy tags input."""
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
    curr_strats = _parse_tag_values(
        raw_value=raw_strats,
        node_id=node_id,
        logger=logger,
        json_loads_fn=json_loads_fn,
        logger_message="Failed to parse strategy_tags JSON for node %s: %s",
    )

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
    """Resolve key-result metrics, tags, and weighting controls."""
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
    curr_inits = _parse_tag_values(
        raw_value=raw_inits,
        node_id=node_id,
        logger=logger,
        json_loads_fn=json_loads_fn,
        logger_message="Failed to parse initiative_tags JSON for node %s: %s",
    )
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
