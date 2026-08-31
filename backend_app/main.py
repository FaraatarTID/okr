# ruff: noqa: E402
"""Internal backend API for secured mutations, timers, and async jobs."""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Response, status  # noqa: F401
from sqlmodel import select  # noqa: F401

from backend_app.job_limits import enforce_job_submit_limits  # noqa: F401
from backend_app.jobs import (  # noqa: F401
    count_dead_jobs,
    enqueue_job,
    get_job,
    list_dead_jobs,
    request_job_cancel,
    retry_dead_job,
    serialize_job,
)
from backend_app.path_setup import ensure_shared_src_on_path
from backend_app.security_state import get_app_state, set_app_state  # noqa: F401
from backend_app.schemas import (
    AtlasSnapshotRequest,
    LeadershipMetricsRequest,
    LoginRequest,
    ReadQueryRequest,
)
from backend_app.security import (
    require_service_access,  # noqa: F401
)
from backend_app.input_normalization import (
    _coerce_datetime,  # noqa: F401
    _normalize_node_type,  # noqa: F401
)
from backend_app.scope_resolution import (
    _coerce_owner_ids as _coerce_owner_ids_impl,
    _coerce_string_list as _coerce_string_list_impl,
    _resolve_actor_scope as _resolve_actor_scope_impl,
)
from backend_app.read_query_helpers import (
    _ALLOWED_READ_QUERY_KINDS as _ALLOWED_READ_QUERY_KINDS_IMPL,
    read_query_payload as _read_query_payload_impl,
)
from backend_app.response_scope_helpers import (
    _filter_tasks_for_scope,  # noqa: F401
    _node_owner_id,  # noqa: F401
    _resolve_goal_owner_id_for_node_via_supabase,  # noqa: F401
    _require_allowed_user_id,  # noqa: F401
    _require_allowed_username,  # noqa: F401
    _serialize_cycle,  # noqa: F401
    _serialize_experiment,  # noqa: F401
    _serialize_goal,  # noqa: F401
    _serialize_key_result,  # noqa: F401
    _serialize_node_for_type,  # noqa: F401
    _serialize_objective,  # noqa: F401
    _serialize_retro,  # noqa: F401
    _serialize_task,  # noqa: F401
    _serialize_team,  # noqa: F401
    _serialize_user,  # noqa: F401
    _serialize_weekly_plan,  # noqa: F401
    _serialize_work_log,  # noqa: F401
)
from backend_app.main_runtime_helpers import (
    _quota_error_code,  # noqa: F401
    _pick_primary_active_cycle as _pick_primary_active_cycle_impl,
    _resolve_scope_for_actor as _resolve_scope_for_actor_impl,
    _list_cycles_for_scope as _list_cycles_for_scope_runtime_impl,
    _scope_role as _scope_role_impl,
    _visible_cycles_for_scope as _visible_cycles_for_scope_impl,
    _require_admin_actor_scope as _require_admin_actor_scope_impl,
    _require_admin_or_manager_actor_scope as _require_admin_or_manager_actor_scope_impl,
    _resolve_actor,  # noqa: F401
    _atomic_idempotent_check as _atomic_idempotent_check_impl,
    _resolve_effective_cycle_id_for_scope as _resolve_effective_cycle_id_for_scope_impl,
    _complete_idempotent_response as _complete_idempotent_response_impl,
    _load_idempotent_response as _load_idempotent_response_impl,
    _store_idempotent_response as _store_idempotent_response_impl,
    _safe_audit_job_submit,  # noqa: F401
    _status_for_value_error,  # noqa: F401
    coerce_int as _coerce_int_impl,
    get_observability_metrics_snapshot,
)
from src.audit import audit_log, error_log  # noqa: F401
from src.audit_queries import summarize_audit_events  # noqa: F401
from src.crud import (
    get_active_cycles,  # noqa: F401
    get_active_experiments_for_kr,  # noqa: F401
    get_active_weekly_plan,  # noqa: F401
    get_all_cycles,  # noqa: F401
    get_all_krs_by_cycle,  # noqa: F401
    get_all_tasks_by_cycle,  # noqa: F401
    get_all_teams,  # noqa: F401
    get_all_users,  # noqa: F401
    get_goal_tree,  # noqa: F401
    get_krs_needing_checkin,  # noqa: F401
    get_node,  # noqa: F401
    get_team_by_id,  # noqa: F401
    get_team_members,  # noqa: F401
    get_team_retrospectives,  # noqa: F401
    get_user_by_id,  # noqa: F401
    get_user_by_username,  # noqa: F401
    get_user_retrospectives,  # noqa: F401
    get_work_logs_by_date_range,  # noqa: F401
    create_goal,  # noqa: F401
    create_objective,  # noqa: F401
    create_key_result,  # noqa: F401
    create_task,  # noqa: F401
    create_user,  # noqa: F401
    create_check_in,  # noqa: F401
    list_experiments_for_kr,  # noqa: F401
    list_experiments_for_retro_window,  # noqa: F401
)
from src.models import (
    AlignmentEdge,  # noqa: F401
    Goal,  # noqa: F401
    KeyResult,  # noqa: F401
    Objective,  # noqa: F401
    User,  # noqa: F401
)
ensure_shared_src_on_path()

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "BACKUP_FORMAT_VERSION",
    "authenticate_user_detailed",
    "get_leadership_metrics",
    "export_database_backup",
    "import_database_backup",
    "get_bool_config",
    "run_ai_health_check",
    "authenticate_user_detailed_via_supabase_api",
    "build_atlas_scope_snapshot_via_supabase_api",
    "get_leadership_metrics_via_supabase_api",
    "get_pdf_runtime_diagnostics",
    "build_atlas_scope_snapshot",
    "is_production_runtime",
    "AtlasSnapshotRequest",
    "LeadershipMetricsRequest",
    "LoginRequest",
    "ReadQueryRequest",
    "get_observability_metrics_snapshot",
]

from src.crud import (
    authenticate_user_detailed,
    close_experiment,  # noqa: F401
    create_alignment,  # noqa: F401
    create_cycle,  # noqa: F401
    create_experiment,  # noqa: F401
    create_objective_alignment_link,  # noqa: F401
    create_retrospective,  # noqa: F401
    create_team,  # noqa: F401
    create_weekly_plan,  # noqa: F401
    delete_alignment,  # noqa: F401
    delete_cycle,  # noqa: F401
    delete_goal,  # noqa: F401
    delete_key_result,  # noqa: F401
    delete_objective,  # noqa: F401
    delete_objective_alignment_link,  # noqa: F401
    delete_task,  # noqa: F401
    delete_team,  # noqa: F401
    delete_work_log,  # noqa: F401
    ensure_admin_exists,
    get_leadership_metrics,
    reset_user_password,  # noqa: F401
    start_timer,  # noqa: F401
    stop_timer,  # noqa: F401
    upsert_retro_experiment_outcome,  # noqa: F401
    update_cycle,  # noqa: F401
    update_experiment,  # noqa: F401
    update_goal,  # noqa: F401
    update_key_result,  # noqa: F401
    update_objective,  # noqa: F401
    update_task,  # noqa: F401
    update_team,  # noqa: F401
    update_user,  # noqa: F401
)
from src.database import (
    BACKUP_FORMAT_VERSION,
    export_database_backup,
    get_session_context,  # noqa: F401
    import_database_backup,
    init_database,
)
from src.config_runtime import get_config_value
from src.domain.password_policy import is_production_runtime
from src.domain.read_queries import build_atlas_scope_snapshot
from src.domain import analysis as analysis_domain
from src.services.ai_provider import run_ai_health_check
from src.services import ai_service
from backend_app.main_mutation_handlers import (
    api_create_goal,  # noqa: F401
    api_create_objective,  # noqa: F401
    api_create_key_result,  # noqa: F401
    api_create_task,  # noqa: F401
    api_create_cycle,  # noqa: F401
    api_create_team,  # noqa: F401
    api_create_user,  # noqa: F401
    api_delete_cycle,  # noqa: F401
    api_delete_node,  # noqa: F401
    api_delete_team,  # noqa: F401
    api_reset_user_password,  # noqa: F401
    api_update_cycle,  # noqa: F401
    api_update_node,  # noqa: F401
    api_update_team,  # noqa: F401
    api_update_user,  # noqa: F401
)
from src.services.supabase_api_mode import (
    authenticate_user_detailed_via_supabase_api,
    build_atlas_scope_snapshot_via_supabase_api,
    ensure_supabase_api_ready,
    is_supabase_api_mode_enabled,
    get_leadership_metrics_via_supabase_api,
    create_goal_via_supabase_api,  # noqa: F401
    create_objective_via_supabase_api,  # noqa: F401
    create_key_result_via_supabase_api,  # noqa: F401
    create_task_via_supabase_api,  # noqa: F401
    create_check_in_via_supabase_api,  # noqa: F401
    create_user_via_supabase_api,  # noqa: F401
    read_query_via_supabase_api,  # noqa: F401
    start_timer_via_supabase_api,  # noqa: F401
    stop_timer_via_supabase_api,  # noqa: F401
)
from src.services.pdf_service import get_pdf_runtime_diagnostics
from backend_app.main_app_bootstrap import build_main_app
from backend_app.main_bootstrap_helpers import validate_runtime_preflight
from backend_app.main_workflow_handlers import (
    api_close_experiment,  # noqa: F401
    api_create_alignment,  # noqa: F401
    api_create_check_in,  # noqa: F401
    api_create_experiment,  # noqa: F401
    api_create_objective_alignment_link,  # noqa: F401
    api_create_retrospective,  # noqa: F401
    api_create_weekly_plan,  # noqa: F401
    api_delete_alignment,  # noqa: F401
    api_delete_objective_alignment_link,  # noqa: F401
    api_delete_work_log,  # noqa: F401
    api_upsert_retro_experiment_outcome,  # noqa: F401
    api_update_experiment,  # noqa: F401
)

analyze_node = ai_service.analyze_node
analyze_team_health = ai_service.analyze_team_health
calculate_burnout_risk = analysis_domain.calculate_burnout_risk
generate_predictive_outlook = ai_service.generate_predictive_outlook
detect_strategy_gaps = analysis_domain.detect_strategy_gaps
 
_ALLOWED_READ_QUERY_KINDS = _ALLOWED_READ_QUERY_KINDS_IMPL


def _resolve_actor_scope(
    session, actor_username: str, token_version: Optional[int] = None
) -> dict[str, Any]:
    return _resolve_actor_scope_impl(
        session,
        actor_username,
        token_version=token_version,
    )


def _scope_role(scope: dict[str, Any]) -> str:
    return _scope_role_impl(scope=scope)


def _visible_cycles_for_scope(scope: dict[str, Any], cycles: list[Any]) -> list[Any]:
    return _visible_cycles_for_scope_impl(scope=scope, cycles=cycles)


def _list_cycles_for_scope(
    *, scope: dict[str, Any], active_only: bool = False
) -> list[Any]:
    return _list_cycles_for_scope_runtime_impl(scope=scope, active_only=active_only)


def _resolve_scope_for_actor(
    actor: str, token_version: Optional[int] = None
) -> dict[str, Any]:
    return _resolve_scope_for_actor_impl(actor=actor, token_version=token_version)


# Unwrapped helper entry points for seam-preserving compatibility checks.
_resolve_actor_scope_runtime = _resolve_actor_scope
_resolve_scope_for_actor_runtime = _resolve_scope_for_actor


def _resolve_effective_cycle_id_for_scope(
    scope: dict[str, Any], requested_cycle_id: Optional[int], *, required: bool = True
) -> Optional[int]:
    return _resolve_effective_cycle_id_for_scope_impl(
        scope=scope,
        requested_cycle_id=requested_cycle_id,
        required=required,
    )


def _pick_primary_active_cycle(
    cycles: list[Any], scope: dict[str, Any] | None = None
) -> Any | None:
    return _pick_primary_active_cycle_impl(cycles=cycles, scope=scope)


def _require_admin_actor_scope(actor: str) -> None:
    return _require_admin_actor_scope_impl(actor=actor)


def _require_admin_or_manager_actor_scope(actor: str) -> None:
    return _require_admin_or_manager_actor_scope_impl(actor=actor)


def _coerce_owner_ids(values: Optional[list[int]]) -> list[int]:
    return _coerce_owner_ids_impl(values=values)


def _coerce_string_list(values: Any) -> list[str]:
    return _coerce_string_list_impl(values=values)


def _coerce_int(value: Any, *, field_name: str) -> int:
    return _coerce_int_impl(value=value, field_name=field_name)


def _atomic_idempotent_check(*, session, actor: str, scope_id: Optional[str], payload: Any) -> tuple[bool, bool]:
    """Compatibility wrapper for request dedupe/idempotency checks."""
    return _atomic_idempotent_check_impl(
        session=session, actor=actor, scope_id=scope_id, payload=payload
    )


def _complete_idempotent_response(
    *, actor: str, response_payload: Any, status_code: int
) -> Any:
    """Compatibility wrapper for idempotent response shaping."""
    return _complete_idempotent_response_impl(
        actor=actor, response_payload=response_payload, status_code=status_code
    )


def _load_idempotent_response(*, actor: str, scope_id: str | None = None) -> Any:
    """Compatibility wrapper for idempotent response load."""
    return _load_idempotent_response_impl(actor=actor, scope_id=scope_id)


def _store_idempotent_response(*, actor: str, response_payload: Any, status_code: int) -> None:
    """Compatibility wrapper for idempotent response storage."""
    return _store_idempotent_response_impl(
        actor=actor, response_payload=response_payload, status_code=status_code
    )


def _read_query_payload(*, kind: str, params: dict, actor: str) -> dict:
    return _read_query_payload_impl(
        kind=kind,
        params=params,
        actor=actor,
        main=sys.modules[__name__],
        allowed_kinds=_ALLOWED_READ_QUERY_KINDS,
    )


def _bootstrap_init_database() -> None:
    return init_database()


def _bootstrap_ensure_admin_exists() -> bool:
    return ensure_admin_exists()


def create_app() -> FastAPI:
    return build_main_app(
        logger=_LOGGER,
        main_module=sys.modules[__name__],
        is_supabase_api_mode_enabled=is_supabase_api_mode_enabled,
        ensure_supabase_api_ready=ensure_supabase_api_ready,
        init_database=_bootstrap_init_database,
        ensure_admin_exists=_bootstrap_ensure_admin_exists,
        validate_runtime_preflight=validate_runtime_preflight,
    )


app = create_app()
