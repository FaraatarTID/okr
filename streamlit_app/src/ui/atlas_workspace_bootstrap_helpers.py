"""Atlas workspace bootstrap orchestration helpers."""

from __future__ import annotations

import logging
from typing import Any, Callable


def resolve_workspace_bootstrap(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    username: str,
    logger: logging.Logger | None,
    resolve_actor_context_fn: Callable[..., tuple[int | None, str]],
    build_scope_options_fn: Callable[..., dict[str, list[int] | None]],
    ensure_scope_selection_fn: Callable[..., str],
    resolve_scope_runtime_fn: Callable[..., dict[str, Any]],
    ensure_selected_ref_fn: Callable[..., str | None],
    sync_selected_navigation_fn: Callable[..., set[str]],
    team_members_loader: Callable[[int], list[Any]],
    all_users_loader: Callable[[], list[Any]],
    runtime_loader: Callable[..., dict[str, Any]],
    canonical_owner_ids_key_fn: Callable[[list[int] | None], Any],
    health_index_builder_fn: Callable[[dict[str, Any]], dict[str, Any]],
    rerun_fn: Callable[[], Any],
) -> dict[str, Any] | None:
    cycle_id = session_state.get("active_cycle_id")
    if not cycle_id:
        st_module.info("Select a cycle to load the OKR workspace.")
        return None

    actor_id, role_value = resolve_actor_context_fn(
        session_state,
        logger=logger,
    )
    if actor_id is None or not role_value:
        st_module.error("User context is unavailable. Please log in again.")
        return None

    scope_options = build_scope_options_fn(
        actor_id=int(actor_id),
        role_value=role_value,
        team_members_loader=team_members_loader,
        all_users_loader=all_users_loader,
    )
    selected_scope = ensure_scope_selection_fn(
        session_state,
        scope_options,
    )
    scope_labels = list(scope_options.keys())

    runtime_data = resolve_scope_runtime_fn(
        cycle_id=int(cycle_id),
        selected_scope=selected_scope,
        scope_options=scope_options,
        runtime_loader=runtime_loader,
        canonical_owner_ids_key=canonical_owner_ids_key_fn,
        health_index_builder=health_index_builder_fn,
        actor_username=username,
    )
    index = runtime_data.get("index", {})
    roots = list(runtime_data.get("roots") or [])
    node_lookup = runtime_data.get("node_lookup") or {}
    session_state["atlas_node_lookup"] = node_lookup

    if not roots:
        st_module.info("No goals found for this cycle and scope.")
        if st_module.button(
            "Create Goal", key="atlas_create_goal_empty", type="primary"
        ):
            session_state["add_mode_parent"] = None
            session_state["add_mode_type"] = "GOAL"
            rerun_fn()
        return None

    selected_ref = ensure_selected_ref_fn(
        session_state,
        index,
        roots,
    )
    if selected_ref is None:
        st_module.info("No selectable nodes found in this scope.")
        return None

    selected_meta = index[selected_ref]
    selected_path_refs = sync_selected_navigation_fn(
        session_state,
        selected_ref=selected_ref,
        selected_meta=selected_meta,
    )

    return {
        "cycle_id": int(cycle_id),
        "actor_id": int(actor_id),
        "role_value": role_value,
        "selected_scope": selected_scope,
        "scope_labels": scope_labels,
        "owner_ids": runtime_data.get("owner_ids"),
        "owner_ids_key": runtime_data.get("owner_ids_key"),
        "index": index,
        "roots": roots,
        "node_lookup": node_lookup,
        "health_index": runtime_data.get("health_index"),
        "runtime_token": runtime_data.get("runtime_token"),
        "selected_ref": selected_ref,
        "selected_meta": selected_meta,
        "selected_path_refs": selected_path_refs,
    }
