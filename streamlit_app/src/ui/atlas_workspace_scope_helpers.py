"""Scope, selection, and task-focus resolution helpers for Atlas workspace."""

from __future__ import annotations

import logging
from typing import Any, Callable


def resolve_actor_context(
    session_state: dict[str, Any],
    *,
    logger: logging.Logger | None = None,
) -> tuple[int | None, str]:
    actor_raw = session_state.get("user_id")
    actor_id: int | None = None
    try:
        actor_id = int(actor_raw) if actor_raw is not None else None
    except (TypeError, ValueError) as exc:
        if logger is not None:
            logger.debug("Failed to coerce session user_id '%s': %s", actor_raw, exc)
        actor_id = None

    role_value = str(session_state.get("user_role") or "").strip().lower()
    return actor_id, role_value


def _active_users(users) -> list[Any]:
    return [
        member for member in (users or []) if bool(getattr(member, "is_active", True))
    ]


def build_scope_options(
    *,
    actor_id: int,
    role_value: str,
    team_members_loader: Callable[[int], list[Any]],
    all_users_loader: Callable[[], list[Any]],
) -> dict[str, list[int] | None]:
    scope_options: dict[str, list[int] | None] = {"My OKRs": [int(actor_id)]}

    if role_value == "manager":
        team_members = _active_users(team_members_loader(int(actor_id)))
        if team_members:
            scope_options["My Team"] = sorted(
                set([int(actor_id)] + [int(member.id) for member in team_members])
            )
            for member in team_members:
                label = f"{member.display_name or member.username} (@{member.username})"
                scope_options[label] = [int(member.id)]
        return scope_options

    if role_value == "admin":
        all_users = _active_users(all_users_loader())
        scope_options["All Users"] = None
        for member in all_users:
            label = f"{member.display_name or member.username} (@{member.username})"
            scope_options[label] = [int(member.id)]
    return scope_options


def ensure_scope_selection(
    session_state: dict[str, Any],
    scope_options: dict[str, list[int] | None],
    *,
    selector_key: str = "atlas_scope_selector",
) -> str:
    scope_labels = list(scope_options.keys())
    if not scope_labels:
        return ""
    if session_state.get(selector_key) not in scope_labels:
        session_state[selector_key] = scope_labels[0]
    return str(session_state.get(selector_key, scope_labels[0]))


def resolve_scope_runtime(
    *,
    cycle_id: int,
    selected_scope: str,
    scope_options: dict[str, list[int] | None],
    runtime_loader: Callable[..., dict[str, Any]],
    canonical_owner_ids_key: Callable[[list[int] | None], Any],
    health_index_builder: Callable[[dict[str, Any]], dict[str, Any]],
    actor_username: str | None = None,
) -> dict[str, Any]:
    owner_ids = scope_options.get(selected_scope)
    owner_ids_key = canonical_owner_ids_key(owner_ids)
    atlas_runtime = runtime_loader(
        int(cycle_id),
        owner_ids_key,
        include_analysis=False,
        actor_username=actor_username,
    )
    index = atlas_runtime.get("index", {})
    roots = list(atlas_runtime.get("roots") or [])
    node_lookup = atlas_runtime.get("node_lookup") or {}
    health_index = atlas_runtime.get("health_index")
    runtime_token = atlas_runtime.get("runtime_token")
    if not isinstance(health_index, dict):
        health_index = health_index_builder(index)

    return {
        "owner_ids": owner_ids,
        "owner_ids_key": owner_ids_key,
        "index": index,
        "roots": roots,
        "node_lookup": node_lookup,
        "health_index": health_index,
        "runtime_token": runtime_token,
    }


def ensure_selected_ref(
    session_state: dict[str, Any],
    index: dict[str, Any],
    roots: list[str],
    *,
    selected_ref_key: str = "atlas_selected_ref",
    nav_stack_key: str = "nav_stack",
) -> str | None:
    selected_ref = session_state.get(selected_ref_key)
    if selected_ref not in index:
        stack = session_state.get(nav_stack_key, [])
        candidate = stack[-1] if stack else None
        selected_ref = (
            candidate if candidate in index else (roots[0] if roots else None)
        )
        if selected_ref is not None:
            session_state[selected_ref_key] = selected_ref
    return selected_ref


def sync_selected_navigation(
    session_state: dict[str, Any],
    *,
    selected_ref: str,
    selected_meta: dict[str, Any],
    nav_stack_key: str = "nav_stack",
    last_selected_key: str = "atlas_last_selected_ref",
    breadcrumbs_key: str = "atlas_breadcrumbs",
) -> set[str]:
    path = list(selected_meta.get("path") or [])
    session_state[nav_stack_key] = path
    if session_state.get(last_selected_key) != selected_ref:
        session_state[last_selected_key] = selected_ref
        session_state[breadcrumbs_key] = selected_ref
    return set(path)


def collect_task_refs(
    *,
    index: dict[str, Any],
    root_ref: str,
    limit: int = 200,
) -> list[str]:
    pending = [root_ref]
    seen = set()
    task_refs: list[str] = []
    while pending and len(task_refs) < int(limit):
        node_ref = pending.pop()
        if node_ref in seen:
            continue
        seen.add(node_ref)
        meta = index.get(node_ref)
        if not meta:
            continue
        if meta.get("type") == "TASK":
            task_refs.append(node_ref)
            continue
        for child_ref in reversed(list(meta.get("children") or [])):
            pending.append(child_ref)
    return task_refs


def suggest_focus_task(
    *,
    task_refs: list[str],
    index: dict[str, Any],
    health_index: dict[str, Any] | None,
    health_state_fn: Callable[..., dict[str, Any]],
) -> str | None:
    if not task_refs:
        return None

    running_refs: list[str] = []
    ranked_refs: list[tuple[int, int, str, str]] = []
    for ref in task_refs:
        meta = index.get(ref)
        if not meta:
            continue
        task = meta.get("node")
        if getattr(task, "timer_started_at", None) is not None:
            running_refs.append(ref)
            continue
        progress = int(meta.get("progress", 0) or 0)
        health = (
            (health_index or {}).get(ref) if isinstance(health_index, dict) else None
        )
        if health is None:
            health = health_state_fn(meta, index=index)
        kind = str(health.get("kind") or "on_track")
        if kind == "overdue":
            bucket = 0
        elif kind in {"risk", "low_progress", "inherited"}:
            bucket = 1
        elif progress >= 100:
            bucket = 3
        else:
            bucket = 2
        ranked_refs.append((bucket, progress, str(meta.get("title_l") or ""), ref))

    if running_refs:
        return running_refs[0]

    ranked_refs.sort()
    return ranked_refs[0][3] if ranked_refs else task_refs[0]


def resolve_focus_task_ref(
    session_state: dict[str, Any],
    *,
    task_refs: list[str],
    suggested_task_ref: str | None,
    focus_task_key: str = "atlas_focus_task_ref",
) -> str | None:
    focus_task_ref = session_state.get(focus_task_key)
    if focus_task_ref not in task_refs:
        focus_task_ref = suggested_task_ref
        if focus_task_ref:
            session_state[focus_task_key] = focus_task_ref
    return focus_task_ref
