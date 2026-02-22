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
    point_labels = [str(lbl) for lbl in (trace.labels or [])] if trace is not None else []
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
