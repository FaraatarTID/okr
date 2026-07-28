"""Runtime API helper wrappers extracted from `backend_app/main.py`."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from backend_app.main_helpers import (
    atomic_idempotent_check,
    audit_experiment_failure,
    coerce_int,
    complete_idempotent_response,
    experiment_view_from_payload,
    get_observability_metrics_snapshot as _get_observability_metrics_snapshot,
    load_idempotent_response_state,
    payload_fingerprint,
    payload_to_jsonable,
    quota_error_code,
    safe_audit_job_submit,
    status_for_value_error,
    idempotency_state_key,
    store_idempotent_response_state,
)
from backend_app.scope_resolution import (
    _coerce_owner_ids as _coerce_owner_ids_impl,
    _coerce_string_list as _coerce_string_list_impl,
    _list_cycles_for_scope as _list_cycles_for_scope_impl,
    _visible_cycles_for_scope as _visible_cycles_for_scope_impl,
    _resolve_actor as _resolve_actor_impl,
    _resolve_actor_scope as _resolve_actor_scope_impl,
    _resolve_effective_cycle_id_for_scope as _resolve_effective_cycle_id_for_scope_impl,
    _resolve_scope_for_actor as _resolve_scope_for_actor_impl,
    _scope_cycle_id as _scope_cycle_id_impl,
    _pick_primary_active_cycle as _pick_primary_active_cycle_impl,
)
from backend_app.main_helpers import validate_experiment_transition as _validate_experiment_transition_impl


def _resolve_actor(
    *, header_actor: Optional[str], payload_actor: Optional[str]
) -> str:
    return _resolve_actor_impl(
        header_actor=header_actor,
        payload_actor=payload_actor,
    )


def _resolve_actor_scope(
    session: Any, actor_username: str, token_version: Optional[int] = None
) -> dict[str, Any]:
    return _resolve_actor_scope_impl(
        session=session,
        actor_username=actor_username,
        token_version=token_version,
    )


def _resolve_scope_for_actor(actor: str, token_version: Optional[int] = None) -> dict[str, Any]:
    from backend_app import main as backend_main

    patched_resolver = getattr(backend_main, "_resolve_scope_for_actor", None)
    baseline_resolver = getattr(backend_main, "_resolve_scope_for_actor_runtime", None)
    if callable(patched_resolver) and baseline_resolver is not None and patched_resolver is not baseline_resolver:
        return patched_resolver(actor, token_version=token_version)

    scoped_resolver = getattr(backend_main, "_resolve_actor_scope", None)
    scoped_runtime = getattr(backend_main, "_resolve_actor_scope_runtime", None)
    if (
        callable(scoped_resolver)
        and scoped_resolver is not _resolve_actor_scope
        and scoped_runtime is not None
        and scoped_resolver is not scoped_runtime
    ):
        with backend_main.get_session_context() as session:
            return scoped_resolver(session, actor, token_version=token_version)
    return _resolve_scope_for_actor_impl(actor=actor, token_version=token_version)


def _resolve_effective_cycle_id_for_scope(
    scope: dict[str, Any], requested_cycle_id: Optional[int], *, required: bool = True
) -> Optional[int]:
    from backend_app import main as backend_main

    list_cycles_for_scope = getattr(backend_main, "_list_cycles_for_scope", None)
    visible_cycles_for_scope = getattr(backend_main, "_visible_cycles_for_scope", None)
    scope_role = getattr(backend_main, "_scope_role", None)

    if (
        callable(list_cycles_for_scope)
        and callable(visible_cycles_for_scope)
        and callable(scope_role)
    ):
        if bool(scope.get("is_admin", False)):
            if requested_cycle_id is None:
                if required:
                    raise HTTPException(status_code=400, detail="cycle_id is required.")
                return None
            return int(requested_cycle_id)

        role = scope_role(scope)
        if role not in {"manager", "member"}:
            if requested_cycle_id is None:
                if required:
                    raise HTTPException(status_code=400, detail="cycle_id is required.")
                return None
            return int(requested_cycle_id)

        if role == "manager":
            if requested_cycle_id is None:
                if required:
                    raise HTTPException(status_code=400, detail="cycle_id is required.")
                return None
            candidate = int(requested_cycle_id)
            owned_cycles = visible_cycles_for_scope(
                scope, list_cycles_for_scope(scope=scope, active_only=False)
            )
            if any(_scope_cycle_id_impl(cycle) == candidate for cycle in owned_cycles):
                return candidate
            raise HTTPException(
                status_code=403, detail="Managers can only use their owned cycles."
            )

        active_cycles = visible_cycles_for_scope(
            scope, list_cycles_for_scope(scope=scope, active_only=True)
        )
        selected = _pick_primary_active_cycle_impl(active_cycles)
        if not selected or _scope_cycle_id_impl(selected) <= 0:
            raise HTTPException(
                status_code=404, detail="No active cycle available for this user scope."
            )
        selected_id = _scope_cycle_id_impl(selected)
        if requested_cycle_id is not None and int(requested_cycle_id) != selected_id:
            raise HTTPException(
                status_code=403,
                detail="Members must use the manager/admin active cycle.",
            )
        return selected_id

    return _resolve_effective_cycle_id_for_scope_impl(
        scope=scope,
        requested_cycle_id=requested_cycle_id,
        required=required,
    )


def _pick_primary_active_cycle(cycles: list[Any]) -> Any | None:
    return _pick_primary_active_cycle_impl(cycles=cycles)


def _require_admin_actor_scope(actor: str) -> None:
    scope = _resolve_scope_for_actor(actor)
    if not bool(scope.get("is_admin", False)):
        raise HTTPException(status_code=403, detail="Admin privileges required.")


def _require_admin_or_manager_actor_scope(actor: str) -> None:
    scope = _resolve_scope_for_actor(actor)
    role = str(scope.get("role") or "").strip().lower()
    if not bool(scope.get("is_admin", False)) and role != "manager":
        raise HTTPException(
            status_code=403, detail="Manager or admin privileges required."
        )


def _coerce_owner_ids(values: Optional[list[int]]) -> list[int]:
    return _coerce_owner_ids_impl(values=values)


def _coerce_string_list(values: Any) -> list[str]:
    return _coerce_string_list_impl(values=values)


def _list_cycles_for_scope(
    *, scope: dict[str, Any], active_only: bool = False
) -> list[Any]:
    from backend_app import main as backend_main

    get_all_cycles = getattr(backend_main, "get_all_cycles", None)
    get_active_cycles = getattr(backend_main, "get_active_cycles", None)
    if callable(get_all_cycles) and callable(get_active_cycles):
        return list(
            get_active_cycles() if active_only else get_all_cycles()
        )
    return _list_cycles_for_scope_impl(scope=scope, active_only=active_only)


def _scope_role(scope: dict[str, Any]) -> str:
    return str(scope.get("role") or "").strip().lower()


def _visible_cycles_for_scope(scope: dict[str, Any], cycles: list[Any]) -> list[Any]:
    return _visible_cycles_for_scope_impl(scope=scope, cycles=cycles)


def _validate_experiment_transition(
    current_status: Any, next_status: Any
) -> None:
    return _validate_experiment_transition_impl(current_status, next_status)


def _payload_to_jsonable(value: Any) -> Any:
    return payload_to_jsonable(value)


def _payload_fingerprint(payload: Any) -> str:
    return payload_fingerprint(payload)


def _idempotency_state_key(*, scope: str, actor: str, key: str) -> str:
    return idempotency_state_key(scope=scope, actor=actor, key=key)


def _load_idempotent_response(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
) -> Optional[dict]:
    return load_idempotent_response_state(
        scope=scope,
        actor=actor,
        idempotency_key=idempotency_key,
        payload=payload,
    )


def _store_idempotent_response(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
    response_payload: dict,
) -> None:
    store_idempotent_response_state(
        scope=scope,
        actor=actor,
        idempotency_key=idempotency_key,
        payload=payload,
        response_payload=response_payload,
    )


def _atomic_idempotent_check(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
) -> Optional[dict]:
    return atomic_idempotent_check(
        scope=scope,
        actor=actor,
        idempotency_key=idempotency_key,
        payload=payload,
    )


def _complete_idempotent_response(
    *,
    scope: str,
    actor: str,
    idempotency_key: Optional[str],
    response_payload: dict,
) -> None:
    complete_idempotent_response(
        scope=scope,
        actor=actor,
        idempotency_key=idempotency_key,
        response_payload=response_payload,
    )


def _audit_experiment_failure(
    *,
    action: str,
    actor: str,
    error_message: str,
    payload: Any,
    idempotency_key: Optional[str],
    experiment_id: Optional[int] = None,
) -> None:
    audit_experiment_failure(
        action=action,
        actor=actor,
        error_message=error_message,
        payload=payload,
        idempotency_key=idempotency_key,
        experiment_id=experiment_id,
    )


def _experiment_view_from_payload(payload: dict) -> Any:
    return experiment_view_from_payload(payload)


def _status_for_value_error(message: str, default: int = 400) -> int:
    return status_for_value_error(message=message, default=default)


def _quota_error_code(detail: Any) -> Optional[str]:
    return quota_error_code(detail)


def _safe_audit_job_submit(
    *,
    action: str,
    actor: str,
    kind: str,
    idempotency_key: Optional[str],
    status_code: int,
    job_id: Optional[str] = None,
    team_id: Optional[int] = None,
    job_status: Optional[str] = None,
    error_code: Optional[str] = None,
    rejection_detail: Optional[Any] = None,
) -> None:
    safe_audit_job_submit(
        action=action,
        actor=actor,
        kind=kind,
        idempotency_key=idempotency_key,
        status_code=status_code,
        job_id=job_id,
        team_id=team_id,
        job_status=job_status,
        error_code=error_code,
        rejection_detail=rejection_detail,
    )


def _coerce_int(value: Any, *, field_name: str) -> int:
    return coerce_int(value=value, field_name=field_name)


def get_observability_metrics_snapshot() -> dict[str, Any]:
    return _get_observability_metrics_snapshot()


__all__ = [
    "_resolve_actor",
    "_resolve_actor_scope",
    "_resolve_scope_for_actor",
    "_resolve_effective_cycle_id_for_scope",
    "_require_admin_actor_scope",
    "_require_admin_or_manager_actor_scope",
    "_coerce_owner_ids",
    "_coerce_string_list",
    "_validate_experiment_transition",
    "_payload_to_jsonable",
    "_payload_fingerprint",
    "_idempotency_state_key",
    "_load_idempotent_response",
    "_store_idempotent_response",
    "_atomic_idempotent_check",
    "_complete_idempotent_response",
    "_audit_experiment_failure",
    "_experiment_view_from_payload",
    "_status_for_value_error",
    "_quota_error_code",
    "_safe_audit_job_submit",
    "_coerce_int",
    "get_observability_metrics_snapshot",
]
