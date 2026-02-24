"""Shared dialog chrome utilities.

Provides reusable CSS and close-header handling for Streamlit dialog modules.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from src.ui import app_query_helpers
from src.ui import session_keys

_STANDARD_DIALOG_CHROME_CSS = """
<style>
div[role="dialog"] button[aria-label="Close"] { display: none; }
div[data-baseweb="modal-backdrop"] { display: none; }
div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
</style>
"""


def get_standard_dialog_chrome_css() -> str:
    """Return the standard dialog chrome CSS payload."""
    return _STANDARD_DIALOG_CHROME_CSS


def _resolve_st_module(st_module: Any | None):
    return st if st_module is None else st_module


def apply_standard_dialog_chrome(*, st_module: Any | None = None) -> None:
    """Inject standard modal chrome CSS for custom dialog close controls."""
    st_ref = _resolve_st_module(st_module)
    st_ref.markdown(get_standard_dialog_chrome_css(), unsafe_allow_html=True)


def render_dialog_header_with_close(
    *,
    close_key: str,
    title_markdown: str | None = None,
    clear_state_keys: tuple[str, ...] = (session_keys.ACTIVE_REPORT_MODE,),
    st_module: Any | None = None,
) -> None:
    """Render common dialog header with close button and session-key cleanup."""
    st_ref = _resolve_st_module(st_module)
    c_head, c_close = st_ref.columns([0.92, 0.08])
    if title_markdown:
        c_head.markdown(title_markdown)
    if c_close.button("", icon=":material/close:", key=close_key):
        for state_key in clear_state_keys:
            if state_key in st_ref.session_state:
                del st_ref.session_state[state_key]
        app_query_helpers.sync_to_query_params(
            st=st_ref,
            session_state=st_ref.session_state,
        )
        st_ref.rerun()
