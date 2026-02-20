"""Ensure backend runtime can import the existing streamlit_app package tree."""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_streamlit_app_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "streamlit_app"
    app_dir_str = str(app_dir)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)
