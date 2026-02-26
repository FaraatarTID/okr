from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_STYLE_DIR = Path(__file__).resolve().parent / "css"


@lru_cache(maxsize=None)
def load_style_block(filename: str) -> str:
    css_path = _STYLE_DIR / filename
    css_body = css_path.read_text(encoding="utf-8")
    return f"<style>\n{css_body}\n</style>"
