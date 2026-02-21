"""Runtime configuration helpers with env + Streamlit secrets fallback."""

from __future__ import annotations

import os
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}


def get_config_value_with_source(name: str, default: Any = "") -> tuple[str, str]:
    """Read config and return (value, source) with env-first precedence."""
    raw = os.getenv(name)
    if raw is not None:
        return str(raw), "env"

    try:
        import streamlit as st  # Imported lazily to keep non-Streamlit contexts safe.

        if name in st.secrets:
            value = st.secrets.get(name, default)
            return str(value if value is not None else default), "secrets_root"

        app_cfg = st.secrets.get("app", {})
        if hasattr(app_cfg, "get") and name in app_cfg:
            value = app_cfg.get(name, default)
            return str(value if value is not None else default), "secrets_app"
    except Exception:
        pass

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
