"""Atlas node-details resolution helpers."""

from __future__ import annotations

from typing import Any, Callable


def resolve_node_details(
    node_id: Any,
    *,
    node_lookup: dict[str, Any] | None,
    session_state: dict[str, Any] | None,
    get_node_details_from_lookup_fn: Callable[..., tuple[str | None, str | None]],
    parse_typed_ref_fn: Callable[[str], tuple[str | None, int | None]],
    get_session_context_fn: Callable[[], Any],
    models_by_type: dict[str, Any],
    logger: Any | None = None,
) -> tuple[str | None, str]:
    lookup_type, lookup_title = get_node_details_from_lookup_fn(
        node_id,
        node_lookup=node_lookup,
        session_state=session_state,
    )
    if lookup_type:
        return lookup_type, str(lookup_title or "Unknown")

    with get_session_context_fn() as session:
        if isinstance(node_id, str) and "_" in node_id:
            node_type, node_id_int = parse_typed_ref_fn(node_id)
            if node_id_int is None:
                return None, "Unknown"
            model = models_by_type.get(str(node_type or "").upper())
            if model is None:
                return None, "Unknown"
            row = session.get(model, node_id_int)
            if row:
                return str(node_type or "").upper(), str(
                    getattr(row, "title", "Unknown")
                )
            return None, "Unknown"

        try:
            raw_id = int(node_id)
        except (TypeError, ValueError) as exc:
            if logger is not None:
                logger.debug("Failed to coerce node id '%s' to int: %s", node_id, exc)
            return None, "Unknown"

        for label in ("GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"):
            model = models_by_type.get(label)
            if model is None:
                continue
            try:
                row = session.get(model, raw_id)
                if row:
                    return label, str(getattr(row, "title", "Unknown"))
            except Exception as exc:
                if logger is not None:
                    logger.debug(
                        "Failed fallback lookup for model %s id=%s: %s",
                        label,
                        raw_id,
                        exc,
                    )
                continue
    return None, "Unknown"
