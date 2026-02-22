"""Helpers for refreshing model bindings after hot-reload events."""

from __future__ import annotations


def ensure_model_bindings_current(
    *,
    module_globals: dict,
    binding_names: tuple[str, ...],
    user_model,
    sa_inspect_fn,
    logger,
) -> None:
    """Refresh local model symbols when SQLModel registry classes are reloaded."""
    import src.models as models_module

    bindings_are_current = True
    for name in binding_names:
        latest = getattr(models_module, name, None)
        if latest is None:
            continue
        if module_globals.get(name) is not latest:
            bindings_are_current = False
            break

    if bindings_are_current:
        try:
            sa_inspect_fn(user_model)
            return
        except Exception as exc:
            logger.debug("Model binding inspect failed; forcing refresh: %s", exc)
            bindings_are_current = False

    if bindings_are_current:
        return

    for name in binding_names:
        value = getattr(models_module, name, None)
        if value is not None:
            module_globals[name] = value
