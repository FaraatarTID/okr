import streamlit as st

from src.ui.style_blocks import (
    atlas_style_block,
    custom_fonts_style_block,
    dialog_style_block,
)

# Hierarchy types (4 levels: Goal -> Objective -> Key Result -> Task)
# Note: Strategy and Initiative are now TAGS, not navigable levels
TYPES = ["GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"]

CHILD_TYPE_MAP = {
    "GOAL": "OBJECTIVE",
    "OBJECTIVE": "KEY_RESULT",
    "KEY_RESULT": "TASK",
    "TASK": None,
}

TYPE_ICONS = {
    "GOAL": "🏁",
    "STRATEGY": "♟️",
    "OBJECTIVE": "🎯",
    "KEY_RESULT": "📊",
    "INITIATIVE": "⚡",
    "TASK": "📋",
}

# Colors for mind map visualization
TYPE_COLORS = {
    "GOAL": "#E53935",  # Red
    "STRATEGY": "#1E88E5",  # Blue
    "OBJECTIVE": "#43A047",  # Green
    "KEY_RESULT": "#FB8C00",  # Orange
    "INITIATIVE": "#8E24AA",  # Purple
    "TASK": "#757575",  # Gray
}

# Size by hierarchy depth (larger for higher-level nodes)
TYPE_SIZES = {
    "GOAL": 35,
    "STRATEGY": 30,
    "OBJECTIVE": 25,
    "KEY_RESULT": 22,
    "INITIATIVE": 18,
    "TASK": 15,
}


def _inject_style_block(style_block: str) -> None:
    st.markdown(style_block, unsafe_allow_html=True)


def inject_dialog_styles():
    """
    CSS to prevent dialog from closing on backdrop click (by hiding the close button backdrop)
    and styling elements inside.
    """
    _inject_style_block(dialog_style_block())


def apply_custom_fonts():
    """
    Injects CSS to enforce Vazirmatn font across the application.
    """
    _inject_style_block(custom_fonts_style_block())


def inject_atlas_styles():
    """Styling tokens for the Atlas timer-first workspace."""
    _inject_style_block(atlas_style_block())
