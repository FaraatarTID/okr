"""Shared chrome helpers for create dialogs."""

from __future__ import annotations

import streamlit as st

_CREATE_DIALOG_BASE_CSS = """
<style>
div[role="dialog"] { position: relative; }
div[role="dialog"] button[aria-label="Close"] { display: none; }
div[data-baseweb="modal-backdrop"] { display: none; }
div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
</style>
"""

_GOAL_CLOSE_BUTTON_CSS = """
<style>
div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    padding: 0 !important;
}

div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
    border-radius: 50% !important;
    border: 1px solid #e0e0e0 !important;
    width: 36px !important;
    height: 36px !important;
    padding: 0 !important;
    margin-left: 8px !important;
    background-color: white !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
}
</style>
"""

_FLOATING_CLOSE_BUTTON_CSS = """
<style>
div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
    position: absolute !important;
    top: 18px !important;
    right: 18px !important;
    z-index: 9999 !important;
    border-radius: 50% !important;
    border: 1px solid #e0e0e0 !important;
    width: 36px !important;
    height: 36px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
    background-color: white !important;
}
</style>
"""


def apply_create_dialog_chrome(*, floating_close_button: bool) -> None:
    """Inject shared create-dialog modal CSS."""
    st.markdown(_CREATE_DIALOG_BASE_CSS, unsafe_allow_html=True)
    extra_css = (
        _FLOATING_CLOSE_BUTTON_CSS if floating_close_button else _GOAL_CLOSE_BUTTON_CSS
    )
    st.markdown(extra_css, unsafe_allow_html=True)


def clear_create_add_mode_state() -> None:
    """Clear create-mode session state keys used by shell navigation."""
    if "add_mode_type" in st.session_state:
        del st.session_state["add_mode_type"]
    if "add_mode_parent" in st.session_state:
        del st.session_state["add_mode_parent"]


def render_create_dialog_close_button(*, close_key: str) -> None:
    """Render close icon button for create dialogs and clear add-mode keys."""
    _, close_col = st.columns([0.92, 0.08])
    if close_col.button("", icon=":material/close:", key=close_key):
        clear_create_add_mode_state()
        st.rerun()
