"""Core facade helpers for phased extraction from crud.py."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Optional

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


def validate_update_fields_from_crud(
    *,
    entity_name: str,
    updates: dict,
    allowed_fields: set,
    crud_module: Optional[Any] = None,
    **_ignored,
) -> None:
    """Raise on update keys that are not explicitly allowed."""
    invalid_fields = sorted(
        [key for key in updates.keys() if key not in allowed_fields]
    )
    if invalid_fields:
        raise ValueError(
            f"Unsupported {entity_name} update fields: {', '.join(invalid_fields)}"
        )
