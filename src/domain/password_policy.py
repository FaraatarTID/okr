"""Shared password policy helpers for auth and API validation."""

from __future__ import annotations

import os
from typing import Optional

from src.config_runtime import get_bool_config


_PRODUCTION_ENV_NAMES = {"prod", "production"}
_STRONG_PASSWORD_MIN_LENGTH = 12


def runtime_env_name() -> str:
    return (
        str(os.getenv("OKR_ENV", os.getenv("OKR_RUNTIME_ENV", "development")))
        .strip()
        .lower()
        or "development"
    )


def is_production_runtime() -> bool:
    return runtime_env_name() in _PRODUCTION_ENV_NAMES


def strong_password_requirements_met(password: str) -> bool:
    return (
        any(ch.islower() for ch in password)
        and any(ch.isupper() for ch in password)
        and any(ch.isdigit() for ch in password)
        and any(not ch.isalnum() for ch in password)
    )


def strict_password_policy_enabled(*, strict: Optional[bool] = None) -> bool:
    if strict is not None:
        return bool(strict)
    return get_bool_config(
        "OKR_ENFORCE_STRONG_PASSWORD_POLICY",
        default=is_production_runtime(),
    )


def validate_password_policy(
    password: str,
    *,
    field_name: str = "Password",
    strict: Optional[bool] = None,
) -> None:
    value = str(password or "")
    if not value:
        raise ValueError(f"{field_name} is required.")

    if not strict_password_policy_enabled(strict=strict):
        return

    if len(value) < _STRONG_PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"{field_name} must be at least {_STRONG_PASSWORD_MIN_LENGTH} characters."
        )
    if not strong_password_requirements_met(value):
        raise ValueError(
            f"{field_name} must include uppercase, lowercase, number, and symbol characters."
        )
