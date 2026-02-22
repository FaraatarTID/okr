"""Inspector dialog shell helpers."""

from __future__ import annotations

from typing import Any


def inject_dialog_css(*, st_module: Any) -> None:
    st_module.markdown(
        """
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button:hover { border-color: #ff4b4b; color: #ff4b4b; background-color: #fff5f5; }
        </style>
    """,
        unsafe_allow_html=True,
    )


def clear_active_inspector(*, session_state: dict[str, Any]) -> None:
    if "active_inspector_id" in session_state:
        del session_state["active_inspector_id"]


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
        clear_active_inspector(session_state=session_state)
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
            clear_active_inspector(session_state=session_state)
            rerun_fn()
        return

    st_module.markdown(f"### {type_icons.get(node_type_upper, '')} {title}")
