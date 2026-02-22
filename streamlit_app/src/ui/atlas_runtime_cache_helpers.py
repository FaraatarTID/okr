"""Helpers for Atlas runtime snapshot/read-cache orchestration."""

from __future__ import annotations

import hashlib
import json


def backend_read_proxy_enabled(*, get_bool_config_fn, logger) -> bool:
    try:
        from src.services.backend_client import is_backend_enabled

        return bool(get_bool_config_fn("OKR_BACKEND_PROXY_READS", False)) and bool(
            is_backend_enabled()
        )
    except Exception as exc:
        logger.debug("Backend read proxy availability check failed: %s", exc)
        return False


def allow_local_backend_fallback(*, get_bool_config_fn, logger) -> bool:
    try:
        from src.config_runtime import get_config_value

        scoped_raw = str(get_config_value("OKR_ALLOW_LOCAL_READ_FALLBACK", "")).strip()
        if scoped_raw:
            return scoped_raw.lower() in {"1", "true", "yes", "on"}
        return bool(get_bool_config_fn("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", False))
    except Exception as exc:
        logger.debug("Local backend fallback check failed: %s", exc)
        return False


def handle_backend_read_failure(
    *,
    operation: str,
    backend_result=None,
    exc: Exception | None = None,
    allow_local_backend_fallback_fn,
    logger,
) -> None:
    detail = None
    if isinstance(backend_result, dict):
        detail = backend_result.get("error")
    if detail is None and exc is not None:
        detail = str(exc)
    detail_text = str(detail or "unknown backend read failure")

    if not allow_local_backend_fallback_fn():
        raise RuntimeError(
            f"Backend read '{operation}' failed and local fallback is disabled: {detail_text}"
        )
    logger.warning(
        "Falling back to local %s read: %s",
        operation,
        detail_text,
    )


def build_scope_snapshot_with_backend_fallback(
    *,
    cycle_id: int,
    owner_ids_key,
    include_analysis: bool,
    actor_username: str | None,
    ensure_model_bindings_current_fn,
    canonical_owner_ids_key_fn,
    backend_read_proxy_enabled_fn,
    handle_backend_read_failure_fn,
    get_session_context_fn,
    build_scope_snapshot_payload_fn,
    goal_model,
    objective_model,
    key_result_model,
    task_model,
    user_model,
    select_fn,
    func_obj,
    extract_ai_snapshot_fields_fn,
):
    ensure_model_bindings_current_fn()
    canonical_owner_ids_key = canonical_owner_ids_key_fn(owner_ids_key)
    if backend_read_proxy_enabled_fn() and actor_username:
        owner_ids = (
            list(canonical_owner_ids_key) if canonical_owner_ids_key is not None else None
        )
        try:
            from src.services.backend_client import fetch_atlas_scope_snapshot

            backend_result = fetch_atlas_scope_snapshot(
                cycle_id=int(cycle_id),
                owner_ids=owner_ids,
                include_analysis=include_analysis,
                actor_username=str(actor_username),
            )
            if isinstance(backend_result, dict) and "error" not in backend_result:
                if isinstance(backend_result.get("goals"), list):
                    return backend_result
            handle_backend_read_failure_fn(
                operation="atlas snapshot",
                backend_result=backend_result,
            )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            handle_backend_read_failure_fn(
                operation="atlas snapshot",
                exc=exc,
            )

    with get_session_context_fn() as session:
        return build_scope_snapshot_payload_fn(
            session=session,
            cycle_id=int(cycle_id),
            canonical_owner_ids_key_value=canonical_owner_ids_key,
            include_analysis=bool(include_analysis),
            goal_model=goal_model,
            objective_model=objective_model,
            key_result_model=key_result_model,
            task_model=task_model,
            user_model=user_model,
            select_fn=select_fn,
            func_obj=func_obj,
            extract_ai_snapshot_fields_fn=extract_ai_snapshot_fields_fn,
        )


def build_scope_runtime_payload(
    *,
    cycle_id: int,
    owner_ids_key,
    include_analysis: bool,
    actor_username: str | None,
    cached_get_scope_snapshot_fn,
    build_atlas_index_from_snapshot_fn,
    build_node_lookup_fn,
    health_index_fn,
):
    snapshot = cached_get_scope_snapshot_fn(
        cycle_id,
        owner_ids_key,
        include_analysis=include_analysis,
        actor_username=actor_username,
    )
    users_map = snapshot.get("users_map", {})
    index, roots = build_atlas_index_from_snapshot_fn(snapshot.get("goals", []), users_map)
    node_lookup = build_node_lookup_fn(index)
    health_index = health_index_fn(index)
    snapshot_json = json.dumps(snapshot, default=str, sort_keys=True, separators=(",", ":"))
    runtime_token = hashlib.sha1(snapshot_json.encode("utf-8")).hexdigest()
    return {
        "snapshot": snapshot,
        "index": index,
        "roots": roots,
        "node_lookup": node_lookup,
        "health_index": health_index,
        "runtime_token": runtime_token,
    }
