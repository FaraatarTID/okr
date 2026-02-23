"""Atlas map chart interaction helpers."""

from __future__ import annotations

from typing import Any, Callable


def build_point_ref_label_lookup(
    *,
    treemap: Any,
    map_refs: list[str],
) -> tuple[list[str], dict[str, list[str]]]:
    trace = treemap.data[0] if getattr(treemap, "data", None) else None
    point_refs = (
        [str(ref) for ref in (trace.ids or [])]
        if trace is not None
        else [str(ref) for ref in map_refs]
    )
    point_labels = (
        [str(lbl) for lbl in (trace.labels or [])] if trace is not None else []
    )
    label_lookup: dict[str, list[str]] = {}
    for idx, label in enumerate(point_labels):
        if idx < len(point_refs):
            label_lookup.setdefault(label, []).append(point_refs[idx])
    return point_refs, label_lookup


def collect_treemap_points(
    *,
    session_state: dict[str, Any],
    chart_key: str,
    chart_events_key: str,
    render_plotly_events_fn: Callable[[], list[Any] | None] | None,
    render_plotly_chart_fn: Callable[[], Any],
    extract_selection_points_fn: Callable[[Any], list[dict[str, Any]]],
    logger: Any,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    rendered_with_events = False

    if render_plotly_events_fn is not None:
        try:
            points = list(render_plotly_events_fn() or [])
            rendered_with_events = True
        except Exception as exc:
            if logger is not None:
                logger.warning(
                    "plotly_events interaction failed; falling back to plotly selection: %s",
                    exc,
                )
            points = []

    if not rendered_with_events:
        treemap_event = render_plotly_chart_fn()
        points = extract_selection_points_fn(treemap_event)
        if not points:
            points = extract_selection_points_fn(session_state.get(chart_key))
    elif not points:
        points = extract_selection_points_fn(session_state.get(chart_events_key))

    return points


def render_plotly_events_points(
    *,
    map_chart_area: Any,
    plotly_events_fn: Callable[..., list[Any] | None],
    treemap: Any,
    chart_events_key: str,
    map_chart_height: int,
) -> list[Any]:
    with map_chart_area:
        return list(
            plotly_events_fn(
                treemap,
                click_event=True,
                select_event=False,
                hover_event=False,
                override_height=int(map_chart_height) + 12,
                override_width="100%",
                key=chart_events_key,
            )
            or []
        )


def apply_clicked_ref_navigation(
    *,
    clicked_ref: str | None,
    selected_ref: str,
    index: dict[str, Any],
    session_state: dict[str, Any],
    health_index: dict[str, Any] | None,
    collect_task_refs_fn: Callable[..., list[str]],
    suggest_focus_task_fn: Callable[..., str | None],
    health_state_fn: Callable[..., dict[str, Any]],
    rerun_fn: Callable[[], Any],
) -> bool:
    if not clicked_ref or clicked_ref not in index or clicked_ref == selected_ref:
        return False

    session_state["atlas_selected_ref"] = clicked_ref
    session_state["atlas_breadcrumbs"] = clicked_ref
    clicked_meta = index[clicked_ref]
    if clicked_meta.get("type") == "TASK":
        session_state["atlas_focus_task_ref"] = clicked_ref
    else:
        branch_tasks = collect_task_refs_fn(
            index=index,
            root_ref=clicked_ref,
            limit=200,
        )
        if branch_tasks:
            session_state["atlas_focus_task_ref"] = (
                suggest_focus_task_fn(
                    task_refs=branch_tasks,
                    index=index,
                    health_index=health_index,
                    health_state_fn=health_state_fn,
                )
                or branch_tasks[0]
            )
    rerun_fn()
    return True


def render_map_chart_and_handle_navigation(
    *,
    map_chart_area: Any,
    session_state: dict[str, Any],
    map_refs: list[str],
    index: dict[str, Any],
    selected_ref: str,
    focus_task_ref: str,
    selected_path_refs: set[str] | list[str] | None,
    health_index: dict[str, Any] | None,
    runtime_token: Any,
    is_mobile_request: bool,
    cached_treemap_fn: Callable[..., Any],
    plotly_events_fn: Callable[..., list[Any] | None] | None,
    extract_selection_points_fn: Callable[[Any], list[dict[str, Any]]],
    extract_clicked_ref_from_points_fn: Callable[..., str | None],
    collect_task_refs_fn: Callable[..., list[str]],
    suggest_focus_task_fn: Callable[..., str | None],
    health_state_fn: Callable[..., dict[str, Any]],
    rerun_fn: Callable[[], Any],
    logger: Any,
) -> bool:
    map_chart_height = 280 if is_mobile_request else 500
    treemap = cached_treemap_fn(
        map_refs,
        index,
        selected_ref,
        focus_task_ref,
        selected_path_refs=selected_path_refs,
        chart_height=map_chart_height,
        health_index=health_index,
        runtime_token=runtime_token,
    )
    if treemap is None:
        map_chart_area.info("No map data available.")
        return False

    chart_key = f"atlas_focus_treemap_{selected_ref}"
    chart_events_key = f"{chart_key}_events"
    point_refs, label_lookup = build_point_ref_label_lookup(
        treemap=treemap,
        map_refs=map_refs,
    )
    points = collect_treemap_points(
        session_state=session_state,
        chart_key=chart_key,
        chart_events_key=chart_events_key,
        render_plotly_events_fn=(
            (
                lambda: render_plotly_events_points(
                    map_chart_area=map_chart_area,
                    plotly_events_fn=plotly_events_fn,
                    treemap=treemap,
                    chart_events_key=chart_events_key,
                    map_chart_height=map_chart_height,
                )
            )
            if plotly_events_fn is not None
            else None
        ),
        render_plotly_chart_fn=lambda: map_chart_area.plotly_chart(
            treemap,
            use_container_width=True,
            config={"displayModeBar": False},
            key=chart_key,
            on_select="rerun",
            selection_mode=("points",),
        ),
        extract_selection_points_fn=extract_selection_points_fn,
        logger=logger,
    )
    clicked_ref = extract_clicked_ref_from_points_fn(
        points,
        index=index,
        current_selected=selected_ref,
        point_refs=point_refs,
        label_lookup=label_lookup,
    )
    apply_clicked_ref_navigation(
        clicked_ref=clicked_ref,
        selected_ref=selected_ref,
        index=index,
        session_state=session_state,
        health_index=health_index,
        collect_task_refs_fn=collect_task_refs_fn,
        suggest_focus_task_fn=suggest_focus_task_fn,
        health_state_fn=health_state_fn,
        rerun_fn=rerun_fn,
    )
    return True


def render_no_tasks_message(
    *,
    sidebar: Any,
    map_task_refs: list[str],
    map_lens: str,
) -> bool:
    if map_task_refs:
        return False
    if map_lens == "Scope":
        sidebar.info("No tasks available in current scope.")
    else:
        sidebar.info("No tasks to choose focus from in this branch.")
    return True
