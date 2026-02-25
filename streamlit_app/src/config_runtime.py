"""Runtime configuration helpers with env + Streamlit secrets fallback."""

from __future__ import annotations

import logging
import os
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}
_LOGGER = logging.getLogger(__name__)


def get_config_value_with_source(name: str, default: Any = "") -> tuple[str, str]:
    """Read config and return (value, source) with env-first precedence."""
    raw = os.getenv(name)
    if raw is not None:
        return str(raw), "env"

    try:
        import streamlit as st  # Imported lazily to keep non-Streamlit contexts safe.

        # 1. Try native Streamlit secrets
        if name in st.secrets:
            value = st.secrets.get(name, default)
            return str(value if value is not None else default), "secrets_root"

        app_cfg = st.secrets.get("app", {})
        if hasattr(app_cfg, "get") and name in app_cfg:
            value = app_cfg.get(name, default)
            return str(value if value is not None else default), "secrets_app"
    except (
        ImportError,
        FileNotFoundError,
        OSError,
        RuntimeError,
        KeyError,
        AttributeError,
    ):
        pass

    # 2. Manual TOML fallback (robust for non-Streamlit processes)
    try:
        # Check standard Streamlit locations: .streamlit/secrets.toml
        # Or streamlit_app/.streamlit/secrets.toml if we are in the root
        possible_paths = [
            os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
            os.path.join(os.getcwd(), "streamlit_app", ".streamlit", "secrets.toml"),
        ]

        # Also check parent directory if we are inside a subfolder
        possible_paths.append(
            os.path.join(os.path.dirname(os.getcwd()), ".streamlit", "secrets.toml")
        )

        import tomllib  # Python 3.11+

        for p in possible_paths:
            if os.path.exists(p):
                with open(p, "rb") as f:
                    data = tomllib.load(f)

                    # Check root
                    if name in data:
                        return str(
                            data[name] if data[name] is not None else default
                        ), f"fs_root:{os.path.basename(p)}"

                    # Check [app]
                    app_data = data.get("app", {})
                    if hasattr(app_data, "get") and name in app_data:
                        val = app_data.get(name)
                        return str(
                            val if val is not None else default
                        ), f"fs_app:{os.path.basename(p)}"
    except Exception as exc:
        _LOGGER.debug("Manual TOML fallback failed for %s: %s", name, exc)

    return str(default), "default"


def get_config_value(name: str, default: Any = "") -> str:
    """Read config with precedence: env -> st.secrets[root] -> st.secrets[app]."""
    value, _source = get_config_value_with_source(name, default)
    return value


def get_bool_config(name: str, default: bool = False) -> bool:
    raw = get_config_value(name, "")
    if not str(raw).strip():
        return bool(default)
    return str(raw).strip().lower() in _TRUE_VALUES


def get_bool_config_with_source(name: str, default: bool = False) -> tuple[bool, str]:
    raw, source = get_config_value_with_source(name, "")
    if not str(raw).strip():
        return bool(default), source
    return (str(raw).strip().lower() in _TRUE_VALUES), source
