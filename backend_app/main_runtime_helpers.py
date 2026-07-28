"""Runtime API helper wrappers extracted from `backend_app/main.py`."""

from __future__ import annotations

from typing import Any, Optional

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
    _resolve_actor as _resolve_actor_impl,
    _resolve_actor_scope as _resolve_actor_scope_impl,
    _resolve_effective_cycle_id_for_scope as _resolve_effective_cycle_id_for_scope_impl,
    _resolve_scope_for_actor as _resolve_scope_for_actor_impl,
    _require_admin_actor_scope as _require_admin_actor_scope_impl,
    _require_admin_or_manager_actor_scope as _require_admin_or_manager_actor_scope_impl,
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

    backend_resolver = getattr(backend_main, "_resolve_scope_for_actor", None)
    if backend_resolver is not None and backend_resolver is not _resolve_scope_for_actor:
        return backend_resolver(actor=actor, token_version=token_version)
    return _resolve_scope_for_actor_impl(actor=actor, token_version=token_version)


def _resolve_effective_cycle_id_for_scope(
    scope: dict[str, Any], requested_cycle_id: Optional[int], *, required: bool = True
) -> Optional[int]:
    from backend_app import main as backend_main

    backend_fn = getattr(backend_main, "_resolve_effective_cycle_id_for_scope", None)
    if backend_fn is not None and backend_fn is not _resolve_effective_cycle_id_for_scope:
        return backend_fn(
            scope=scope,
            requested_cycle_id=requested_cycle_id,
            required=required,
        )
    return _resolve_effective_cycle_id_for_scope_impl(
        scope=scope,
        requested_cycle_id=requested_cycle_id,
        required=required,
    )


def _require_admin_actor_scope(actor: str) -> None:
    from backend_app import main as backend_main

    backend_fn = getattr(backend_main, "_require_admin_actor_scope", None)
    if backend_fn is not None and backend_fn is not _require_admin_actor_scope:
        return backend_fn(actor)
    return _require_admin_actor_scope_impl(actor=actor)


def _require_admin_or_manager_actor_scope(actor: str) -> None:
    from backend_app import main as backend_main

    backend_fn = getattr(backend_main, "_require_admin_or_manager_actor_scope", None)
    if backend_fn is not None and backend_fn is not _require_admin_or_manager_actor_scope:
        return backend_fn(actor)
    return _require_admin_or_manager_actor_scope_impl(actor=actor)


def _coerce_owner_ids(values: Optional[list[int]]) -> list[int]:
    return _coerce_owner_ids_impl(values=values)


def _coerce_string_list(values: Any) -> list[str]:
    return _coerce_string_list_impl(values=values)


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
