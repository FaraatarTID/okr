"""Ensure backend runtime can import the shared `src` package tree."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_shared_src_on_path() -> None:
    os.environ.setdefault("OKR_RUNTIME_ROLE", "backend")
    repo_root = Path(__file__).resolve().parents[1]
    shared_src_dir = repo_root / "src"
    repo_root_str = str(repo_root)

    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    if not shared_src_dir.exists():
        raise RuntimeError(
            "Missing shared runtime package at repo-root 'src/'. "
            "This deployment does not support legacy path fallback."
        )
