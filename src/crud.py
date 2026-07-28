"""Facade CRUD layer for the OKR application.

This module is intentionally a stable compatibility surface, not the primary home
of business logic. Most concrete behavior has been sliced into focused helper
modules (`crud_*_helpers.py`), while this file preserves import paths used across:
1. UI modules and dialogs that call `src.crud` directly.
2. Tests that monkeypatch symbols on the `src.crud` module object.
3. Backend proxy adapters that depend on legacy function signatures.

Why delegation still flows through this file:
1. Backward compatibility: existing callers do not need to change imports.
2. Policy centralization: shared config flags and allowed update fields stay visible.
3. Runtime rebinding: helpers receive `crud_module=sys.modules[__name__]` so they
   can resolve symbols dynamically from this module during tests/hot reload.
"""

from __future__ import annotations

from sqlmodel import Session, select  # noqa: F401
from sqlalchemy.orm import selectinload  # noqa: F401
import logging
from datetime import datetime  # noqa: F401
from typing import List, Optional  # noqa: F401
from src.utils.time_utils import utc_now_naive  # noqa: F401

# NOTE:
# Many imports below intentionally suppress Ruff unused-import checks. Helpers read
# attributes from this module object at runtime (via `crud_module=...`), so names
# that appear unused inside this file are still part of the runtime contract.
from src.models import (
    Goal,  # noqa: F401
    Objective,  # noqa: F401
    KeyResult,  # noqa: F401
    Task,  # noqa: F401
    TaskStatus,  # noqa: F401
    Cycle,  # noqa: F401
    CheckIn,  # noqa: F401
    User,  # noqa: F401
    UserRole,  # noqa: F401
    WeeklyPlan,  # noqa: F401
    Retrospective,  # noqa: F401
    Team,  # noqa: F401
    AlignmentEdge,  # noqa: F401
    VariationType,  # noqa: F401
    ExperimentDecision,  # noqa: F401
    ExpectedEffectDirection,  # noqa: F401
    Experiment,  # noqa: F401
    RetroExperimentOutcome,  # noqa: F401
)
from src.config_runtime import get_bool_config, get_config_value  # noqa: F401
from src.database import get_session_context as _database_get_session_context  # noqa: F401
from src.domain import authorization as domain_auth  # noqa: F401
from src.audit import audit_log  # noqa: F401
from src.utils.cache_utils import clear_cache_safe  # noqa: F401

from src import crud_runtime_helpers as _crud_runtime_helpers
from src import crud_auth_helpers as _crud_auth_helpers

# Helper modules own concrete implementations per domain slice.
# This facade delegates to them while preserving legacy call signatures.
from src import crud_timer_facade as _crud_timer_facade
from src import crud_read_facade as _crud_read_facade
from src import crud_mutation_facade as _crud_mutation_facade
from src.domain.crud_contracts import (
    ALLOWED_EXPERIMENT_UPDATE_FIELDS,
    ALLOWED_GOAL_UPDATE_FIELDS,
    ALLOWED_KEY_RESULT_UPDATE_FIELDS,
    ALLOWED_OBJECTIVE_UPDATE_FIELDS,
    ALLOWED_TASK_UPDATE_KWARGS,
    ADMIN_BOOTSTRAP_MAX_RETRIES as _ADMIN_BOOTSTRAP_MAX_RETRIES,
    ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS as _ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS,
    AUTH_IP_MAX_ATTEMPTS as _AUTH_IP_MAX_ATTEMPTS,
    AUTH_IP_WINDOW_SECONDS as _AUTH_IP_WINDOW_SECONDS,
    AUTH_LOCKOUT_SECONDS as _AUTH_LOCKOUT_SECONDS,
    AUTH_USER_MAX_ATTEMPTS as _AUTH_USER_MAX_ATTEMPTS,
    AUTH_USER_WINDOW_SECONDS as _AUTH_USER_WINDOW_SECONDS,
    BOOTSTRAP_ADMIN_PASSWORD_ENV,
    MODEL_BINDING_NAMES,
    UNSET,
)

logger = logging.getLogger(__name__)


# Field allow-lists are explicit mutation contracts. Update helpers validate
# incoming kwargs against these sets to prevent silent schema drift.
_ALLOWED_GOAL_UPDATE_FIELDS = ALLOWED_GOAL_UPDATE_FIELDS
_ALLOWED_OBJECTIVE_UPDATE_FIELDS = ALLOWED_OBJECTIVE_UPDATE_FIELDS
_ALLOWED_KEY_RESULT_UPDATE_FIELDS = ALLOWED_KEY_RESULT_UPDATE_FIELDS
_ALLOWED_TASK_UPDATE_KWARGS = ALLOWED_TASK_UPDATE_KWARGS
_ALLOWED_EXPERIMENT_UPDATE_FIELDS = ALLOWED_EXPERIMENT_UPDATE_FIELDS
_UNSET = UNSET
AUTH_USER_WINDOW_SECONDS = _AUTH_USER_WINDOW_SECONDS
AUTH_USER_MAX_ATTEMPTS = _AUTH_USER_MAX_ATTEMPTS
AUTH_IP_WINDOW_SECONDS = _AUTH_IP_WINDOW_SECONDS
AUTH_IP_MAX_ATTEMPTS = _AUTH_IP_MAX_ATTEMPTS
AUTH_LOCKOUT_SECONDS = _AUTH_LOCKOUT_SECONDS
ADMIN_BOOTSTRAP_MAX_RETRIES = _ADMIN_BOOTSTRAP_MAX_RETRIES
ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS = _ADMIN_BOOTSTRAP_RETRY_DELAY_SECONDS
_BOOTSTRAP_ADMIN_PASSWORD_ENV = BOOTSTRAP_ADMIN_PASSWORD_ENV
_MODEL_BINDING_NAMES = MODEL_BINDING_NAMES

# ---------------------------------------------------------------------------
# Core facade adapters
# ---------------------------------------------------------------------------
# These wrappers are intentionally delegated to a dedicated runtime adapter
# module to keep ownership boundaries clear while preserving this facade contract.


_ensure_model_bindings_current = _crud_runtime_helpers._ensure_model_bindings_current
get_session_context = _crud_runtime_helpers.get_session_context
_backend_mutation_proxy_enabled = _crud_runtime_helpers._backend_mutation_proxy_enabled
_backend_read_proxy_enabled = _crud_runtime_helpers._backend_read_proxy_enabled
_resolve_backend_actor = _crud_runtime_helpers._resolve_backend_actor
_raise_backend_read_error = _crud_runtime_helpers._raise_backend_read_error
_backend_read_result_or_raise = _crud_runtime_helpers._backend_read_result_or_raise
_local_backend_fallback_allowed = _crud_runtime_helpers._local_backend_fallback_allowed
_is_transient_backend_mutation_error = _crud_runtime_helpers._is_transient_backend_mutation_error
_raise_backend_mutation_error = _crud_runtime_helpers._raise_backend_mutation_error
_enforce_backend_mutation_failure_policy = _crud_runtime_helpers._enforce_backend_mutation_failure_policy
_node_from_backend_payload = _crud_runtime_helpers._node_from_backend_payload
_validate_update_fields = _crud_runtime_helpers._validate_update_fields


# Read/query facade exports (delegated for ownership clarity)
get_all_users = _crud_read_facade.get_all_users
get_user_by_id = _crud_read_facade.get_user_by_id
get_team_members = _crud_read_facade.get_team_members
get_check_ins = _crud_read_facade.get_check_ins
get_krs_needing_checkin = _crud_read_facade.get_krs_needing_checkin
list_experiments_for_kr = _crud_read_facade.list_experiments_for_kr
get_active_experiments_for_kr = _crud_read_facade.get_active_experiments_for_kr
list_experiments_for_retro_window = _crud_read_facade.list_experiments_for_retro_window
get_active_cycles = _crud_read_facade.get_active_cycles
get_all_cycles = _crud_read_facade.get_all_cycles
get_dashboard_data = _crud_read_facade.get_dashboard_data
get_goal_tree = _crud_read_facade.get_goal_tree
get_user_goals_simple = _crud_read_facade.get_user_goals_simple
get_node = _crud_read_facade.get_node
get_node_by_external_id = _crud_read_facade.get_node_by_external_id
get_leadership_metrics = _crud_read_facade.get_leadership_metrics
get_work_logs_by_date_range = _crud_read_facade.get_work_logs_by_date_range
get_all_krs_by_cycle = _crud_read_facade.get_all_krs_by_cycle
get_all_tasks_by_cycle = _crud_read_facade.get_all_tasks_by_cycle
get_hours_by_goal = _crud_read_facade.get_hours_by_goal
get_daily_work_trend = _crud_read_facade.get_daily_work_trend
get_active_weekly_plan = _crud_read_facade.get_active_weekly_plan
get_user_retrospectives = _crud_read_facade.get_user_retrospectives
get_team_retrospectives = _crud_read_facade.get_team_retrospectives
get_user_data_from_sql = _crud_read_facade.get_user_data_from_sql
get_sql_id_by_external = _crud_read_facade.get_sql_id_by_external
get_all_teams = _crud_read_facade.get_all_teams
get_team_by_id = _crud_read_facade.get_team_by_id

# Timer/work-log facade exports (delegated for ownership clarity)
_get_active_work_log_for_task = _crud_timer_facade._get_active_work_log_for_task
_query_owned_task_for_timer = _crud_timer_facade._query_owned_task_for_timer
_stop_all_active_timers = _crud_timer_facade._stop_all_active_timers
add_manual_log = _crud_timer_facade.add_manual_log
delete_work_log = _crud_timer_facade.delete_work_log
force_stop_active_timers = _crud_timer_facade.force_stop_active_timers
get_active_timer = _crud_timer_facade.get_active_timer
get_total_time = _crud_timer_facade.get_total_time
get_work_log_by_start_time = _crud_timer_facade.get_work_log_by_start_time
start_timer = _crud_timer_facade.start_timer
stop_timer = _crud_timer_facade.stop_timer


# ============================================================================
# USER OPERATIONS (Authentication & Authorization)
# ============================================================================
# The auth section contains both public APIs (create/auth/update user) and
# internal guardrail primitives used by helper modules for throttling/RBAC.
# Implementation is delegated across helper modules (`src.crud_runtime_helpers`,
# `src.crud_auth_helpers`) to keep ownership boundaries clear.
_auth_throttle_fail_open_allowed = _crud_runtime_helpers._auth_throttle_fail_open_allowed
_resolve_bootstrap_admin_password = _crud_runtime_helpers._resolve_bootstrap_admin_password
hash_password = _crud_runtime_helpers.hash_password
verify_password = _crud_runtime_helpers.verify_password
create_user = _crud_runtime_helpers.create_user
get_user_by_username = _crud_runtime_helpers.get_user_by_username

_goal_owner_predicate_by_username = _crud_auth_helpers._goal_owner_predicate_by_username
_goal_owner_predicate_by_user_id = _crud_auth_helpers._goal_owner_predicate_by_user_id
_timer_owner_predicate_by_username = _crud_auth_helpers._timer_owner_predicate_by_username
_can_manage_goal = _crud_auth_helpers._can_manage_goal
_can_manage_owner = _crud_auth_helpers._can_manage_owner
_resolve_goal_for_node = _crud_auth_helpers._resolve_goal_for_node
_authorize_node_mutation = _crud_auth_helpers._authorize_node_mutation
_authorize_node_scoped_access = _crud_auth_helpers._authorize_node_scoped_access
get_user_goals = _crud_auth_helpers.get_user_goals
_require_actor_user = _crud_auth_helpers._require_actor_user
_require_admin_actor = _crud_auth_helpers._require_admin_actor
_authorize_self_or_admin = _crud_auth_helpers._authorize_self_or_admin
_normalize_throttle_username = _crud_auth_helpers._normalize_throttle_username
_normalize_client_ip = _crud_auth_helpers._normalize_client_ip
_get_auth_throttle_states = _crud_auth_helpers._get_auth_throttle_states
_new_auth_throttle_state = _crud_auth_helpers._new_auth_throttle_state
_remaining_lockout_seconds = _crud_auth_helpers._remaining_lockout_seconds
_prepare_throttle_state_for_check = _crud_auth_helpers._prepare_throttle_state_for_check
_record_failed_auth_attempt = _crud_auth_helpers._record_failed_auth_attempt
_clear_auth_throttle_state = _crud_auth_helpers._clear_auth_throttle_state
_is_auth_throttle_operational_error = _crud_auth_helpers._is_auth_throttle_operational_error
_is_auth_throttle_schema_operational_error = (
    _crud_auth_helpers._is_auth_throttle_schema_operational_error
)
_is_transient_connection_operational_error = (
    _crud_auth_helpers._is_transient_connection_operational_error
)
_authenticate_user_without_throttle = _crud_auth_helpers._authenticate_user_without_throttle
authenticate_user_detailed = _crud_auth_helpers.authenticate_user_detailed
authenticate_user = _crud_auth_helpers.authenticate_user

update_user = _crud_mutation_facade.update_user
reset_user_password = _crud_mutation_facade.reset_user_password
_ensure_admin_exists_once = _crud_mutation_facade._ensure_admin_exists_once
ensure_admin_exists = _crud_mutation_facade.ensure_admin_exists
create_check_in = _crud_mutation_facade.create_check_in
create_experiment = _crud_mutation_facade.create_experiment
update_experiment = _crud_mutation_facade.update_experiment
close_experiment = _crud_mutation_facade.close_experiment
create_cycle = _crud_mutation_facade.create_cycle
update_cycle = _crud_mutation_facade.update_cycle
delete_cycle = _crud_mutation_facade.delete_cycle
create_goal = _crud_mutation_facade.create_goal
create_objective = _crud_mutation_facade.create_objective
create_key_result = _crud_mutation_facade.create_key_result
create_task = _crud_mutation_facade.create_task
update_goal = _crud_mutation_facade.update_goal
update_key_result_analysis = _crud_mutation_facade.update_key_result_analysis
update_objective = _crud_mutation_facade.update_objective
create_alignment = _crud_mutation_facade.create_alignment
delete_alignment = _crud_mutation_facade.delete_alignment
create_objective_alignment_link = _crud_mutation_facade.create_objective_alignment_link
delete_objective_alignment_link = _crud_mutation_facade.delete_objective_alignment_link
update_key_result = _crud_mutation_facade.update_key_result
update_task = _crud_mutation_facade.update_task
delete_goal = _crud_mutation_facade.delete_goal
delete_task = _crud_mutation_facade.delete_task
delete_objective = _crud_mutation_facade.delete_objective
delete_key_result = _crud_mutation_facade.delete_key_result
calculate_progress = _crud_mutation_facade.calculate_progress
update_progress_chain = _crud_mutation_facade.update_progress_chain
recalculate_rollup_for_key_results = _crud_mutation_facade.recalculate_rollup_for_key_results
create_weekly_plan = _crud_mutation_facade.create_weekly_plan
create_retrospective = _crud_mutation_facade.create_retrospective
upsert_retro_experiment_outcome = _crud_mutation_facade.upsert_retro_experiment_outcome
create_team = _crud_mutation_facade.create_team
update_team = _crud_mutation_facade.update_team
delete_team = _crud_mutation_facade.delete_team

# ============================================================================
# TIMER OPERATIONS
# ============================================================================
# Timer and work-log APIs are delegated to `src.crud_timer_facade` for ownership
# boundaries while preserving legacy `src.crud` symbol availability.




# ============================================================================
# PROGRESS CALCULATIONS
# ============================================================================
# Rollup functions keep hierarchy progress coherent after task/check-in updates.
