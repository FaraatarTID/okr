"""Runtime configuration helpers with env + TOML fallback."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}
_LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _candidate_config_paths() -> tuple[Path, ...]:
    repo_root = Path(__file__).resolve().parents[1]
    candidates: list[Path] = []

    explicit_path = str(
        os.getenv("OKR_SECRETS_FILE", os.getenv("OKR_CONFIG_FILE", ""))
    ).strip()
    if explicit_path:
        candidates.append(Path(explicit_path))

    candidates.extend(
        [
            repo_root / "deploy" / "secrets" / "secrets.toml",
            Path.cwd() / "deploy" / "secrets" / "secrets.toml",
            Path.cwd() / "secrets.toml",
        ]
    )

    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        normalized = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(candidate)
    return tuple(unique)


@lru_cache(maxsize=8)
def _load_toml(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.exists():
        return {}

    try:
        import tomllib
    except ModuleNotFoundError:
        return {}

    try:
        with path.open("rb") as fh:
            payload = tomllib.load(fh)
    except Exception as exc:
        _LOGGER.debug("Config TOML read failed (%s): %s", path, exc)
        return {}

    if not isinstance(payload, dict):
        return {}
    return payload


def get_config_value_with_source(name: str, default: Any = "") -> tuple[str, str]:
    """Read config and return (value, source) with env-first precedence."""
    raw = os.getenv(name)
    if raw is not None:
        return str(raw), "env"

    # Streamlit secrets fallback (useful during Streamlit runtime and testing)
    try:
        import sys
        if "streamlit" in sys.modules:
            st = sys.modules["streamlit"]
            if hasattr(st, "secrets") and st.secrets:
                # Direct check
                try:
                    if name in st.secrets:
                        val = st.secrets[name]
                        return str(val if val is not None else default), "streamlit_secrets"
                except Exception:
                    pass
                # Section check
                try:
                    if hasattr(st.secrets, "get"):
                        app_cfg = st.secrets.get("app", {})
                        if isinstance(app_cfg, dict) and name in app_cfg:
                            val = app_cfg.get(name)
                            return str(val if val is not None else default), "secrets_app"
                except Exception:
                    pass
    except Exception:
        pass


    for path in _candidate_config_paths():
        data = _load_toml(str(path))
        if not data:
            continue

        if name in data:
            value = data.get(name)
            return str(value if value is not None else default), f"toml_root:{path.name}"

        app_cfg = data.get("app", {})
        if isinstance(app_cfg, dict) and name in app_cfg:
            value = app_cfg.get(name)
            return str(value if value is not None else default), f"toml_app:{path.name}"

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
