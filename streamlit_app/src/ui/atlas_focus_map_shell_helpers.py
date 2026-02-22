"""Atlas focus map shell/layout helpers."""

from __future__ import annotations

from typing import Any, Callable


def create_workspace_tabs(st_module: Any) -> tuple[Any, Any]:
    return tuple(st_module.tabs(["Focus Map", "Inspector"]))


def render_focus_map_shell(
    *,
    st_module: Any,
    selected_meta: dict[str, Any],
    node_lookup: dict[str, Any],
    type_icons: dict[str, str],
    get_node_details_fn: Callable[..., tuple[str | None, str]],
    escape_html_fn: Callable[[str], str],
    is_mobile_request: bool,
) -> tuple[Any, Any]:
    st_module.markdown("<div class='atlas-kicker'>Focus Map</div>", unsafe_allow_html=True)
    st_module.caption("Navigate hierarchy and pick your next move.")

    nav_labels = ["Home"]
    for path_ref in selected_meta.get("path", []):
        node_type, node_title = get_node_details_fn(path_ref, node_lookup=node_lookup)
        if not node_type:
            continue
        nav_labels.append(f"{type_icons.get(node_type, '')} {node_title}")
    st_module.markdown(
        f"<div class='atlas-nav-line'>{escape_html_fn(' > '.join(nav_labels))}</div>",
        unsafe_allow_html=True,
    )

    map_placeholder = st_module.empty()
    with map_placeholder.container():
        if is_mobile_request:
            map_chart_area = st_module.container()
            map_sidebar_area = st_module.container()
        else:
            map_cols = st_module.columns([2.25, 1.05], gap="large")
            map_chart_area = map_cols[0]
            map_sidebar_area = map_cols[1]
    return map_chart_area, map_sidebar_area
