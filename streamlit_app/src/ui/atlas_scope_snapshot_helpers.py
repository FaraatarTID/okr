"""Atlas scope snapshot query/payload helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.domain.read_queries import build_atlas_scope_snapshot


def canonical_owner_ids_key(owner_ids):
    if owner_ids is None:
        return None
    canonical = sorted(
        {int(owner_id) for owner_id in owner_ids if owner_id is not None}
    )
    return tuple(canonical)


def build_scope_snapshot_payload(
    *,
    session: Any,
    cycle_id: int,
    canonical_owner_ids_key_value,
    include_analysis: bool,
    goal_model: Any,
    objective_model: Any,
    key_result_model: Any,
    task_model: Any,
    user_model: Any,
    select_fn: Callable[..., Any],
    func_obj: Any,
    extract_ai_snapshot_fields_fn: Callable[[Any], tuple[int | None, str | None]],
) -> dict[str, Any]:
    # Keep legacy injected parameters accepted for compatibility while routing
    # logic through the shared domain query builder.
    _ = (
        goal_model,
        objective_model,
        key_result_model,
        task_model,
        user_model,
        select_fn,
        func_obj,
    )
    owner_ids = (
        list(canonical_owner_ids_key_value)
        if canonical_owner_ids_key_value is not None
        else None
    )
    return build_atlas_scope_snapshot(
        session,
        cycle_id=int(cycle_id),
        owner_ids=owner_ids,
        include_analysis=include_analysis,
        extract_ai_snapshot_fields_fn=extract_ai_snapshot_fields_fn,
    )
