"""Ensure backend runtime can import the shared `src` package tree."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Load env vars from deploy/docker/.env if present (no override of existing)."""
    repo_root = Path(__file__).resolve().parents[1]
    env_file = repo_root / "deploy" / "docker" / ".env"
    if not env_file.exists():
        return
    try:
        with env_file.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        _LOGGER.warning("Failed to load env file %s; environment variables may be missing", env_file, exc_info=True)


def ensure_shared_src_on_path() -> None:
    _load_env_file()
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
