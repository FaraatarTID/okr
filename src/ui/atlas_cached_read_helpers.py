"""Generic cached read helper implementations for UI wrappers."""

from __future__ import annotations

import os


def cached_get_all_tasks_by_cycle(cycle_id, *, limit=None, offset=0):
    from src.crud import get_all_tasks_by_cycle

    return get_all_tasks_by_cycle(cycle_id, limit=limit, offset=offset)


def cycle_task_scan_limit(*, logger, default: int = 2000) -> int:
    """
    Soft guardrail for cycle-wide scans in dashboard widgets.

    Keeps UI queries bounded while remaining configurable for larger deployments.
    """
    raw = str(os.getenv("OKR_UI_CYCLE_TASK_SCAN_LIMIT", str(default))).strip()
    try:
        value = int(raw)
    except Exception as exc:
        logger.debug("Invalid OKR_UI_CYCLE_TASK_SCAN_LIMIT '%s': %s", raw, exc)
        value = int(default)
    return max(100, int(value))


def cached_get_all_krs_by_cycle(cycle_id):
    from src.crud import get_all_krs_by_cycle

    return get_all_krs_by_cycle(cycle_id)


def cached_get_all_users():
    from src.crud import get_all_users

    return get_all_users()


def cached_get_team_members(manager_id):
    from src.crud import get_team_members

    return get_team_members(manager_id)


def cached_get_work_logs_by_range(user_id, start_dt, end_dt):
    from src.crud import get_work_logs_by_date_range

    return get_work_logs_by_date_range(user_id, start_dt, end_dt)


def cached_get_node(node_id, node_type, *, actor_username=None):
    from src.crud import get_node

    return get_node(node_id, node_type, actor_username=actor_username)


def cached_get_user_by_id(user_id):
    from src.crud import get_user_by_id

    return get_user_by_id(user_id)


def cached_get_work_logs(
    task_id,
    *,
    actor_username=None,
    ensure_model_bindings_current_fn,
    get_session_context_fn,
    select_fn,
    worklog_model,
):
    from src.services import backend_client

    _ = (
        ensure_model_bindings_current_fn,
        get_session_context_fn,
        select_fn,
        worklog_model,
    )
    actor = backend_client.resolve_actor_username(actor_username)
    backend_result = backend_client.read_work_logs_by_task(
        int(task_id),
        actor_username=actor,
    )
    if isinstance(backend_result, dict) and "error" in backend_result:
        raise RuntimeError(str(backend_result.get("error") or "Backend read failed."))
    return list(backend_result or [])
