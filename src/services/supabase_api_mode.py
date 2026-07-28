"""Compatibility facade for Supabase HTTPS API mode helpers.

Ownership of transport, read, mutation, and node logic now lives in dedicated
service slices. This module re-exports the canonical symbols so external seams and
monkeypatch points stay stable for legacy tests and call sites.
"""

from __future__ import annotations

from src.services import (
    supabase_api_mode_atlas,
    supabase_api_mode_mutation,
    supabase_api_mode_nodes,
    supabase_api_mode_operations,
    supabase_api_mode_read,
    supabase_api_mode_transport,
)

build_atlas_scope_snapshot_via_supabase_api = (
    supabase_api_mode_atlas.build_atlas_scope_snapshot_via_supabase_api
)
get_leadership_metrics_via_supabase_api = (
    supabase_api_mode_atlas.get_leadership_metrics_via_supabase_api
)
read_query_via_supabase_api = supabase_api_mode_read.read_query_via_supabase_api

create_alignment_via_supabase_api = (
    supabase_api_mode_operations.create_alignment_via_supabase_api
)
create_cycle_via_supabase_api = supabase_api_mode_operations.create_cycle_via_supabase_api
create_check_in_via_supabase_api = (
    supabase_api_mode_operations.create_check_in_via_supabase_api
)
create_experiment_via_supabase_api = (
    supabase_api_mode_operations.create_experiment_via_supabase_api
)
close_experiment_via_supabase_api = (
    supabase_api_mode_operations.close_experiment_via_supabase_api
)
create_retrospective_via_supabase_api = (
    supabase_api_mode_operations.create_retrospective_via_supabase_api
)
reset_user_password_via_supabase_api = (
    supabase_api_mode_operations.reset_user_password_via_supabase_api
)
start_timer_via_supabase_api = supabase_api_mode_operations.start_timer_via_supabase_api
stop_timer_via_supabase_api = supabase_api_mode_operations.stop_timer_via_supabase_api
upsert_retro_experiment_outcome_via_supabase_api = (
    supabase_api_mode_operations.upsert_retro_experiment_outcome_via_supabase_api
)
update_cycle_via_supabase_api = supabase_api_mode_operations.update_cycle_via_supabase_api
update_experiment_via_supabase_api = (
    supabase_api_mode_operations.update_experiment_via_supabase_api
)
get_experiment_via_supabase_api = (
    supabase_api_mode_operations.get_experiment_via_supabase_api
)
create_weekly_plan_via_supabase_api = (
    supabase_api_mode_operations.create_weekly_plan_via_supabase_api
)
create_user_via_supabase_api = supabase_api_mode_operations.create_user_via_supabase_api
update_user_via_supabase_api = supabase_api_mode_operations.update_user_via_supabase_api
delete_alignment_via_supabase_api = (
    supabase_api_mode_operations.delete_alignment_via_supabase_api
)
delete_cycle_via_supabase_api = (
    supabase_api_mode_operations.delete_cycle_via_supabase_api
)

create_team_via_supabase_api = supabase_api_mode_mutation.create_team_via_supabase_api
delete_team_via_supabase_api = supabase_api_mode_mutation.delete_team_via_supabase_api
update_team_via_supabase_api = supabase_api_mode_mutation.update_team_via_supabase_api

authenticate_user_detailed_via_supabase_api = (
    supabase_api_mode_nodes.authenticate_user_detailed_via_supabase_api
)
create_goal_via_supabase_api = supabase_api_mode_nodes.create_goal_via_supabase_api
create_key_result_via_supabase_api = (
    supabase_api_mode_nodes.create_key_result_via_supabase_api
)
create_objective_via_supabase_api = (
    supabase_api_mode_nodes.create_objective_via_supabase_api
)
create_task_via_supabase_api = supabase_api_mode_nodes.create_task_via_supabase_api
update_node_via_supabase_api = supabase_api_mode_nodes.update_node_via_supabase_api
delete_node_via_supabase_api = supabase_api_mode_nodes.delete_node_via_supabase_api

is_supabase_api_mode_enabled = supabase_api_mode_transport.is_supabase_api_mode_enabled
_base_url = supabase_api_mode_transport._base_url
_api_key = supabase_api_mode_transport._api_key
_get_ssl_context = supabase_api_mode_transport._get_ssl_context
_request_json = supabase_api_mode_transport._request_json
_request_json_with_method = supabase_api_mode_transport._request_json_with_method
_rest_select = supabase_api_mode_transport._rest_select
_rest_insert = supabase_api_mode_transport._rest_insert
_rest_update = supabase_api_mode_transport._rest_update
_rest_delete = supabase_api_mode_transport._rest_delete
_as_int = supabase_api_mode_transport._as_int
_in_clause_ids = supabase_api_mode_transport._in_clause_ids
_parse_dt = supabase_api_mode_transport._parse_dt
_to_int_score = supabase_api_mode_transport._to_int_score
_coerce_progress = supabase_api_mode_transport._coerce_progress
_coerce_float = supabase_api_mode_transport._coerce_float
_recalculate_objective_progress_via_supabase = (
    supabase_api_mode_transport._recalculate_objective_progress_via_supabase
)
_recalculate_goal_progress_via_supabase = (
    supabase_api_mode_transport._recalculate_goal_progress_via_supabase
)
_deadline_status_code_fast = supabase_api_mode_transport._deadline_status_code_fast
_count_rows = supabase_api_mode_transport._count_rows
_atlas_extract_ai_snapshot_fields = (
    supabase_api_mode_transport._atlas_extract_ai_snapshot_fields
)
_first_user_by_username = supabase_api_mode_transport._first_user_by_username
_decorate_node_row = supabase_api_mode_transport._decorate_node_row
_coerce_payload_value = supabase_api_mode_transport._coerce_payload_value
_role_for_storage = supabase_api_mode_transport._role_for_storage
_normalize_user_row_role = supabase_api_mode_transport._normalize_user_row_role
_utc_now_iso = supabase_api_mode_transport._utc_now_iso
_date_only_iso = supabase_api_mode_transport._date_only_iso
_cycle_owner_column_supported = supabase_api_mode_transport._cycle_owner_column_supported
_cycle_select_fields = supabase_api_mode_transport._cycle_select_fields
ensure_supabase_api_ready = supabase_api_mode_transport.ensure_supabase_api_ready
