from __future__ import annotations

from src.ui.style_blocks.loader import load_style_block


def dialog_style_block() -> str:
    return load_style_block("dialog.css")
