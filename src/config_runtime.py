"""Runtime configuration helpers (env-only)."""

from __future__ import annotations

import logging
import os
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}
_LOGGER = logging.getLogger(__name__)


def get_config_value_with_source(name: str, default: Any = "") -> tuple[str, str]:
    """Read config from environment variables only."""
    raw = os.getenv(name)
    if raw is not None:
        return str(raw), "env"

    return str(default), "default"


def get_config_value(name: str, default: Any = "") -> str:
    """Read config with precedence: env -> TOML root -> TOML app."""
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
