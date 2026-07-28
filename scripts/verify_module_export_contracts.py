#!/usr/bin/env python3
"""Verify compatibility export contracts for façade and adapter modules."""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("OKR_ENFORCE_ROUTE_BOOTSTRAP_ASSERT", "0")


EXPECTED_EXPORTS: dict[str, list[str]] = {
    "backend_app.main": [
        "app",
        "create_app",
        "api_create_goal",
        "api_create_objective",
        "api_create_key_result",
        "api_create_task",
        "api_create_cycle",
        "api_create_team",
        "api_create_user",
        "api_delete_cycle",
        "api_delete_node",
        "api_delete_team",
        "api_reset_user_password",
        "api_update_cycle",
        "api_update_node",
        "api_update_team",
        "api_update_user",
        "api_close_experiment",
        "api_create_check_in",
        "api_create_experiment",
        "api_create_weekly_plan",
        "api_create_alignment",
        "api_delete_alignment",
        "api_delete_objective_alignment_link",
        "api_create_objective_alignment_link",
        "api_delete_work_log",
        "api_upsert_retro_experiment_outcome",
        "api_update_experiment",
        "api_create_retrospective",
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
        "create_goal_via_supabase_api",
        "create_objective_via_supabase_api",
        "create_key_result_via_supabase_api",
        "create_task_via_supabase_api",
        "create_check_in_via_supabase_api",
        "start_timer_via_supabase_api",
        "stop_timer_via_supabase_api",
        "read_query_via_supabase_api",
        "ensure_supabase_api_ready",
        "is_supabase_api_mode_enabled",
        "build_atlas_scope_snapshot",
        "is_production_runtime",
        "get_observability_metrics_snapshot",
        "BACKUP_FORMAT_VERSION",
        "_resolve_actor_scope",
        "_resolve_scope_for_actor",
        "_resolve_effective_cycle_id_for_scope",
        "_require_admin_actor_scope",
        "_require_admin_or_manager_actor_scope",
        "_coerce_owner_ids",
        "_coerce_string_list",
        "_read_query_payload",
        "_ALLOWED_READ_QUERY_KINDS",
    ],
    "backend_app.main_bootstrap_helpers": [
        "make_main_lifespan",
        "register_main_routers",
    ],
    "backend_app.main_runtime_helpers": [
        "_resolve_actor",
        "_resolve_actor_scope",
        "_resolve_scope_for_actor",
        "_resolve_effective_cycle_id_for_scope",
        "_require_admin_actor_scope",
        "_require_admin_or_manager_actor_scope",
        "_coerce_owner_ids",
        "_coerce_string_list",
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
    ],
    "backend_app.main_mutation_handlers": [
        "_resolve_backend_main",
        "api_create_goal",
        "api_create_objective",
        "api_create_key_result",
        "api_update_node",
        "api_delete_node",
        "api_create_user",
        "api_update_user",
        "api_reset_user_password",
        "api_create_cycle",
        "api_update_cycle",
        "api_delete_cycle",
        "api_create_team",
        "api_update_team",
        "api_delete_team",
        "api_create_task",
    ],
    "backend_app.main_workflow_handlers": [
        "_resolve_backend_main",
        "api_create_check_in",
        "api_create_experiment",
        "api_update_experiment",
        "api_close_experiment",
        "api_create_retrospective",
        "api_upsert_retro_experiment_outcome",
        "api_create_weekly_plan",
        "api_create_alignment",
        "api_delete_alignment",
        "api_create_objective_alignment_link",
        "api_delete_objective_alignment_link",
        "api_delete_work_log",
    ],
    "src.crud_auth_helpers": [
        "authenticate_user_detailed",
        "authenticate_user",
        "_authorize_node_mutation",
        "_authorize_node_scoped_access",
    ],
    "src.crud_runtime_helpers": [
        "_backend_mutation_proxy_enabled",
        "_backend_read_proxy_enabled",
        "hash_password",
        "verify_password",
        "get_user_by_username",
    ],
}

MANDATORY_CALLABLES: dict[str, list[str]] = {
    "backend_app.main": ["create_app", "_resolve_actor_scope", "_coerce_int", "api_create_goal"],
    "backend_app.main_bootstrap_helpers": ["make_main_lifespan", "register_main_routers"],
    "backend_app.main_runtime_helpers": ["get_observability_metrics_snapshot", "_coerce_int"],
    "backend_app.main_mutation_handlers": ["_resolve_backend_main", "api_create_goal"],
    "backend_app.main_workflow_handlers": ["_resolve_backend_main", "api_create_experiment"],
    "src.crud_auth_helpers": ["authenticate_user_detailed", "authenticate_user"],
    "src.crud_runtime_helpers": ["hash_password", "verify_password", "get_user_by_username"],
}


def _find_duplicate_entries(values: list[str], module_name: str, context: str) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen:
            duplicates.append(f"{module_name}: duplicate {context} '{value}'")
        seen.add(value)
    return duplicates


def _check_all_dunder_exports(module_obj: object, module_name: str, issues: list[str]) -> None:
    raw_exports = getattr(module_obj, "__all__", [])
    if not isinstance(raw_exports, (list, tuple)):
        return

    normalized = [str(item) for item in raw_exports]
    issues.extend(_find_duplicate_entries(normalized, module_name, "export"))


def check() -> int:
    issues: list[str] = []
    for module_name, expected in EXPECTED_EXPORTS.items():
        try:
            module_obj = importlib.import_module(module_name)
        except Exception as exc:
            issues.append(f"{module_name}: failed to import ({exc})")
            continue

        issues.extend(
            _find_duplicate_entries(expected, module_name, "manifest export")
        )

        for symbol in expected:
            if not hasattr(module_obj, symbol):
                issues.append(f"{module_name}: required export '{symbol}' is missing")

        expected_callable = MANDATORY_CALLABLES.get(module_name, [])
        for symbol in expected_callable:
            if not hasattr(module_obj, symbol):
                continue
            if not callable(getattr(module_obj, symbol)):
                issues.append(f"{module_name}: required export '{symbol}' must be callable")

        _check_all_dunder_exports(module_obj, module_name, issues)

        if not inspect.ismodule(module_obj):
            issues.append(f"{module_name}: failed module import sanity check")
            continue

        for symbol in expected:
            if symbol.startswith("__"):
                issues.append(
                    f"{module_name}: expected export '{symbol}' uses private dunder style and should be reviewed"
                )

    if issues:
        for issue in issues:
            print(f"[CONTRACT] {issue}")
        return 1

    print("[PASS] Module export contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
