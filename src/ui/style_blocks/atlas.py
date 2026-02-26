from __future__ import annotations

from src.ui.style_blocks.loader import load_style_block


def atlas_style_block() -> str:
    return load_style_block("atlas.css")
