from __future__ import annotations

from src.ui.style_blocks.loader import load_style_block


def custom_fonts_style_block() -> str:
    return load_style_block("custom_fonts.css")
