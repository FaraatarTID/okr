"""Core facade helpers for phased extraction from crud.py."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Dict

from sqlalchemy import inspect as sa_inspect


def ensure_model_bindings_current_from_crud(*, crud_module) -> None:
    """Refresh class bindings after hot-reload if registry classes were replaced."""
    import src.models as _models

    bindings_are_current = True
    for name in crud_module._MODEL_BINDING_NAMES:
        latest = getattr(_models, name, None)
        if latest is None:
            continue
        if crud_module.__dict__.get(name) is not latest:
            bindings_are_current = False
            break

    if bindings_are_current:
        try:
            sa_inspect(crud_module.User)
            return
        except Exception as exc:
            crud_module.logger.debug(
                "Model binding inspect failed in CRUD; forcing refresh: %s", exc
            )
            bindings_are_current = False

    if bindings_are_current:
        return

    for name in crud_module._MODEL_BINDING_NAMES:
        value = getattr(_models, name, None)
        if value is not None:
            setattr(crud_module, name, value)


@contextmanager
def get_session_context_from_crud(*, crud_module):
    ensure_model_bindings_current_from_crud(crud_module=crud_module)
    with crud_module._database_get_session_context() as session:
        yield session


def backend_mutation_proxy_enabled_from_crud(*, crud_module) -> bool:
    try:
        from src.services.backend_client import is_backend_enabled

        return bool(is_backend_enabled())
    except Exception as exc:
        crud_module.logger.debug(
            "Backend mutation proxy availability check failed: %s", exc
        )
        return False


def local_backend_fallback_allowed_from_crud(*, crud_module) -> bool:
    return False


def is_transient_backend_mutation_error_from_crud(
    *, crud_module, payload: Dict[str, Any]
) -> bool:
    try:
        code = int(payload.get("status_code") or 0)
    except Exception as exc:
        crud_module.logger.debug(
            "Failed to parse backend mutation status_code '%s': %s",
            payload.get("status_code"),
            exc,
        )
        code = 0
    if code == 0 or code in {500, 502, 503, 504}:
        return True
    message = str(payload.get("error") or "").strip().lower()
    return any(
        token in message
        for token in {
            "connection",
            "timed out",
            "timeout",
            "temporar",
            "unavailable",
            "refused",
        }
    )


def raise_backend_mutation_error_from_crud(
    *, crud_module, payload: Dict[str, Any]
) -> None:
    message = str(payload.get("error") or "Backend mutation failed.").strip()
    try:
        code = int(payload.get("status_code") or 0)
    except Exception as exc:
        crud_module.logger.debug(
            "Failed to parse backend mutation status_code for raise '%s': %s",
            payload.get("status_code"),
            exc,
        )
        code = 0
    if code in {401, 403}:
        raise PermissionError(message)
    if code == 404:
        raise ValueError(message or "Target not found.")
    raise ValueError(message)


def enforce_backend_mutation_failure_policy_from_crud(
    *, crud_module, payload: Dict[str, Any]
) -> None:
    if not is_transient_backend_mutation_error_from_crud(
        crud_module=crud_module,
        payload=payload,
    ):
        raise_backend_mutation_error_from_crud(
            crud_module=crud_module,
            payload=payload,
        )
    
    message = str(
        payload.get("error") or "Backend mutation request failed."
    ).strip()
    raise ValueError(
        f"{message} Local backend fallback is disabled; retry when backend is healthy."
    )


def node_from_backend_payload_from_crud(*, payload: Dict[str, Any]):
    node_data = payload.get("node")
    if isinstance(node_data, dict):
        return SimpleNamespace(**node_data)
    return SimpleNamespace(**{k: v for k, v in payload.items() if k != "status_code"})


def validate_update_fields_from_crud(
    *, entity_name: str, updates: dict, allowed_fields: set
) -> None:
    """Raise on update keys that are not explicitly allowed."""
    invalid_fields = sorted(
        [key for key in updates.keys() if key not in allowed_fields]
    )
    if invalid_fields:
        raise ValueError(
            f"Unsupported {entity_name} update fields: {', '.join(invalid_fields)}"
        )
