"""Inspector dialog shell helpers."""

from __future__ import annotations

from typing import Any

from src.ui import app_query_helpers
from src.ui import dialog_chrome_helpers


def inject_dialog_css(*, st_module: Any) -> None:
    st_module.markdown(
        dialog_chrome_helpers.get_standard_dialog_chrome_css()
        + """
        <style>
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button:hover { border-color: #ff4b4b; color: #ff4b4b; background-color: #fff5f5; }
        </style>
    """,
        unsafe_allow_html=True,
    )


def clear_active_inspector(
    *,
    session_state: dict[str, Any],
    st_module: Any | None = None,
) -> None:
    if "active_inspector_id" in session_state:
        del session_state["active_inspector_id"]
    if st_module is None:
        return
    app_query_helpers.sync_to_query_params(st=st_module, session_state=session_state)


def handle_missing_node(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    node_id: int,
    node_type: str,
    rerun_fn: Any,
) -> bool:
    st_module.error(f"Node {node_id} ({node_type}) not found")
    if st_module.button("Close", key=f"close_error_{node_id}"):
        clear_active_inspector(session_state=session_state, st_module=st_module)
        rerun_fn()
    return True


def derive_node_context(
    *,
    node: Any,
    node_type: str,
) -> dict[str, Any]:
    node_type_insp = str(node_type or "").upper()
    has_children_insp = False
    if node_type_insp == "GOAL" and hasattr(node, "objectives"):
        has_children_insp = len(getattr(node, "objectives") or []) > 0
    elif node_type_insp == "OBJECTIVE" and hasattr(node, "key_results"):
        has_children_insp = len(getattr(node, "key_results") or []) > 0
    elif node_type_insp == "KEY_RESULT" and hasattr(node, "tasks"):
        has_children_insp = len(getattr(node, "tasks") or []) > 0

    return {
        "title": getattr(node, "title", ""),
        "progress": getattr(node, "progress", 0),
        "node_type_upper": node_type_insp,
        "has_children": has_children_insp,
    }


def render_header(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    show_close: bool,
    node_id: int,
    node_type_upper: str,
    title: str,
    type_icons: dict[str, str],
    rerun_fn: Any,
) -> None:
    if show_close:
        c_head_insp, c_close_insp = st_module.columns([0.92, 0.08])
        c_head_insp.markdown(f"### {type_icons.get(node_type_upper, '')} {title}")
        if c_close_insp.button(
            "",
            icon=":material/close:",
            key=f"close_insp_{node_id}",
        ):
            clear_active_inspector(session_state=session_state, st_module=st_module)
            rerun_fn()
        return

    st_module.markdown(f"### {type_icons.get(node_type_upper, '')} {title}")
