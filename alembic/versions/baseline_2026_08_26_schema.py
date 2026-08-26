"""Baseline schema: per-manager active cycles (squashed history).

Squashes all prior migrations into a single baseline. The schema includes the
per-manager active-cycle model: ux_cycle_owner_active partial unique index
ensures at most one ACTIVE cycle per owner (owner_manager_id).

Revision ID: baseline_2026_08_26
Revises: None
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "baseline_2026_08_26"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _all_tables() -> list[str]:
    from sqlalchemy import inspect

    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return []


_RLS_EXCLUDED = {
    "alembic_version",
    "spa_users",
    "audit_log_entries",
    "identities",
    "sessions",
    "mfa_factors",
    "mfa_challenges",
    "mfa_amr_claims",
    "refresh_tokens",
    "schema_migrations",
    "flow_state",
    "sso_providers",
    "sso_domains",
    "keys",
}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _create_all_fallback() -> None:
    """SQLite path: build the schema from SQLModel metadata (same models,
    including the partial unique indexes)."""
    from src.database import SQLModel
    from src.database import _create_engine

    url = op.get_bind().engine.url.render_as_string(hide_password=False)
    engine = _create_engine(url)
    try:
        SQLModel.metadata.create_all(engine)
    finally:
        engine.dispose()


def upgrade() -> None:
    if not _is_postgres():
        # SQLite (tests/dev): build schema from the same models (including
        # partial unique indexes) instead of Postgres-dialect DDL.
        _create_all_fallback()
        return
    op.execute("""\
CREATE TYPE asyncjobstatus AS ENUM (
    'pending',
    'running',
    'succeeded',
    'failed',
    'cancelled'
)
""")
    op.execute("""\
CREATE TABLE audit_event (
	id SERIAL NOT NULL, 
	actor VARCHAR, 
	actor_user_id INTEGER, 
	actor_role VARCHAR, 
	actor_team_id INTEGER, 
	action VARCHAR NOT NULL, 
	entity VARCHAR NOT NULL, 
	result VARCHAR NOT NULL, 
	details_json VARCHAR NOT NULL, 
	target_type VARCHAR, 
	target_id INTEGER, 
	target_owner_id INTEGER, 
	target_team_id INTEGER, 
	correlation_id VARCHAR, 
	request_id VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_action ON audit_event (action)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_action_entity ON audit_event (action, entity)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor ON audit_event (actor)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor_created ON audit_event (actor, created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor_role ON audit_event (actor_role)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor_role_created ON audit_event (actor_role, created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor_team_id ON audit_event (actor_team_id)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor_team_id_created ON audit_event (actor_team_id, created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor_user_id ON audit_event (actor_user_id)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_actor_user_id_created ON audit_event (actor_user_id, created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_correlation_id ON audit_event (correlation_id)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_created_at ON audit_event (created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_entity ON audit_event (entity)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_request_id ON audit_event (request_id)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_result ON audit_event (result)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_result_created ON audit_event (result, created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_target_id ON audit_event (target_id)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_target_owner_created ON audit_event (target_owner_id, created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_target_owner_id ON audit_event (target_owner_id)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_target_team_created ON audit_event (target_team_id, created_at)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_target_team_id ON audit_event (target_team_id)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_target_type ON audit_event (target_type)
""")
    op.execute("""\
CREATE INDEX ix_audit_event_target_type_id ON audit_event (target_type, target_id)
""")
    op.execute("""\
CREATE TABLE auth_throttle_state (
	id SERIAL NOT NULL, 
	scope VARCHAR NOT NULL, 
	identifier VARCHAR NOT NULL, 
	failed_attempts INTEGER NOT NULL, 
	window_started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	locked_until TIMESTAMP WITHOUT TIME ZONE, 
	last_failed_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_auth_throttle_failed_attempts_non_negative CHECK (failed_attempts >= 0)
)
""")
    op.execute("""\
CREATE INDEX ix_auth_throttle_locked_until ON auth_throttle_state (locked_until)
""")
    op.execute("""\
CREATE INDEX ix_auth_throttle_state_identifier ON auth_throttle_state (identifier)
""")
    op.execute("""\
CREATE INDEX ix_auth_throttle_state_scope ON auth_throttle_state (scope)
""")
    op.execute("""\
CREATE UNIQUE INDEX ux_auth_throttle_scope_identifier ON auth_throttle_state (scope, identifier)
""")
    op.execute("""\
CREATE TABLE team (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	description VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)
""")
    op.execute("""\
CREATE UNIQUE INDEX ix_team_name ON team (name)
""")
    op.execute("""\
CREATE TABLE async_job (
	id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	status asyncjobstatus NOT NULL, 
	actor_username VARCHAR, 
	team_id INTEGER, 
	idempotency_key VARCHAR, 
	payload_json VARCHAR NOT NULL, 
	result_json VARCHAR, 
	error_text VARCHAR, 
	attempts INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	cancel_requested BOOLEAN NOT NULL, 
	worker_id VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(team_id) REFERENCES team (id)
)
""")
    op.execute("""\
CREATE INDEX ix_async_job_actor_created ON async_job (actor_username, created_at)
""")
    op.execute("""\
CREATE INDEX ix_async_job_actor_username ON async_job (actor_username)
""")
    op.execute("""\
CREATE INDEX ix_async_job_cancel_requested ON async_job (cancel_requested)
""")
    op.execute("""\
CREATE INDEX ix_async_job_created_at ON async_job (created_at)
""")
    op.execute("""\
CREATE INDEX ix_async_job_id ON async_job (id)
""")
    op.execute("""\
CREATE INDEX ix_async_job_idempotency_key ON async_job (idempotency_key)
""")
    op.execute("""\
CREATE INDEX ix_async_job_kind ON async_job (kind)
""")
    op.execute("""\
CREATE INDEX ix_async_job_status ON async_job (status)
""")
    op.execute("""\
CREATE INDEX ix_async_job_status_created ON async_job (status, created_at)
""")
    op.execute("""\
CREATE INDEX ix_async_job_status_finished ON async_job (status, finished_at)
""")
    op.execute("""\
CREATE INDEX ix_async_job_team_created ON async_job (team_id, created_at)
""")
    op.execute("""\
CREATE INDEX ix_async_job_team_id ON async_job (team_id)
""")
    op.execute("""\
CREATE INDEX ix_async_job_worker_id ON async_job (worker_id)
""")
    op.execute("""\
CREATE UNIQUE INDEX ux_async_job_actor_kind_idempotency ON async_job (actor_username, kind, idempotency_key) WHERE idempotency_key IS NOT NULL
""")
    op.execute("""\
CREATE TABLE "user" (
	id SERIAL NOT NULL, 
	username VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	must_change_password BOOLEAN NOT NULL, 
	password_changed_at TIMESTAMP WITHOUT TIME ZONE, 
	display_name VARCHAR, 
	role userrole NOT NULL, 
	manager_id INTEGER, 
	team_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	token_version INTEGER NOT NULL DEFAULT 1, 
	PRIMARY KEY (id), 
	FOREIGN KEY(manager_id) REFERENCES "user" (id), 
	FOREIGN KEY(team_id) REFERENCES team (id)
)
""")
    op.execute("""\
CREATE INDEX ix_user_manager_active ON "user" (manager_id, is_active)
""")
    op.execute("""\
CREATE INDEX ix_user_must_change_password ON "user" (must_change_password)
""")
    op.execute("""\
CREATE INDEX ix_user_team_id ON "user" (team_id)
""")
    op.execute("""\
CREATE INDEX ix_user_token_version ON "user" (token_version)
""")
    op.execute("""\
CREATE UNIQUE INDEX ix_user_username ON "user" (username)
""")
    op.execute("""\
CREATE TABLE cycle (
	id SERIAL NOT NULL, 
	title VARCHAR NOT NULL, 
	start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	end_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	owner_manager_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_manager_id) REFERENCES "user" (id)
)
""")
    op.execute("""\
CREATE INDEX ix_cycle_is_active ON cycle (is_active)
""")
    op.execute("""\
CREATE INDEX ix_cycle_owner_manager_active ON cycle (owner_manager_id, is_active)
""")
    op.execute("""\
CREATE INDEX ix_cycle_owner_manager_id ON cycle (owner_manager_id)
""")
    op.execute("""\
CREATE INDEX ix_cycle_title ON cycle (title)
""")
    op.execute("""\
CREATE UNIQUE INDEX ux_cycle_owner_active ON cycle (owner_manager_id) WHERE is_active
""")
    op.execute("""\
CREATE TABLE weekly_plan (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	week_start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	week_end_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	priority_1 VARCHAR NOT NULL, 
	priority_2 VARCHAR, 
	priority_3 VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES "user" (id)
)
""")
    op.execute("""\
CREATE INDEX ix_weekly_plan_user_date ON weekly_plan (user_id, week_start_date)
""")
    op.execute("""\
CREATE INDEX ix_weekly_plan_user_id ON weekly_plan (user_id)
""")
    op.execute("""\
CREATE TABLE goal (
	title VARCHAR NOT NULL, 
	description VARCHAR, 
	progress INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	team_id INTEGER, 
	created_by VARCHAR, 
	updated_by VARCHAR, 
	is_expanded BOOLEAN NOT NULL, 
	external_id VARCHAR, 
	deadline TIMESTAMP WITHOUT TIME ZONE, 
	id SERIAL NOT NULL, 
	owner_id INTEGER NOT NULL, 
	cycle_id INTEGER, 
	strategy_tags VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_goal_progress_range CHECK (progress >= 0 AND progress <= 100), 
	FOREIGN KEY(team_id) REFERENCES team (id), 
	FOREIGN KEY(owner_id) REFERENCES "user" (id), 
	FOREIGN KEY(cycle_id) REFERENCES cycle (id)
)
""")
    op.execute("""\
CREATE INDEX ix_goal_cycle_id ON goal (cycle_id)
""")
    op.execute("""\
CREATE INDEX ix_goal_external_id ON goal (external_id)
""")
    op.execute("""\
CREATE INDEX ix_goal_owner_cycle ON goal (owner_id, cycle_id)
""")
    op.execute("""\
CREATE INDEX ix_goal_owner_id ON goal (owner_id)
""")
    op.execute("""\
CREATE INDEX ix_goal_team_id ON goal (team_id)
""")
    op.execute("""\
CREATE INDEX ix_goal_title ON goal (title)
""")
    op.execute("""\
CREATE TABLE retrospective (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	cycle_id INTEGER, 
	week_start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	content VARCHAR NOT NULL, 
	sentiment VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES "user" (id), 
	FOREIGN KEY(cycle_id) REFERENCES cycle (id)
)
""")
    op.execute("""\
CREATE INDEX ix_retrospective_cycle_id ON retrospective (cycle_id)
""")
    op.execute("""\
CREATE INDEX ix_retrospective_user_id ON retrospective (user_id)
""")
    op.execute("""\
CREATE INDEX ix_retrospective_week_start_date ON retrospective (week_start_date)
""")
    op.execute("""\
CREATE TABLE objective (
	title VARCHAR NOT NULL, 
	description VARCHAR, 
	progress INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	owner_id INTEGER, 
	team_id INTEGER, 
	created_by VARCHAR, 
	updated_by VARCHAR, 
	is_expanded BOOLEAN NOT NULL, 
	external_id VARCHAR, 
	deadline TIMESTAMP WITHOUT TIME ZONE, 
	id SERIAL NOT NULL, 
	goal_id INTEGER NOT NULL, 
	weight FLOAT NOT NULL, 
	score_mode scoremode NOT NULL, 
	state lifecyclestate NOT NULL, 
	final_reflection VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_objective_progress_range CHECK (progress >= 0 AND progress <= 100), 
	FOREIGN KEY(owner_id) REFERENCES "user" (id), 
	FOREIGN KEY(team_id) REFERENCES team (id), 
	FOREIGN KEY(goal_id) REFERENCES goal (id)
)
""")
    op.execute("""\
CREATE INDEX ix_objective_external_id ON objective (external_id)
""")
    op.execute("""\
CREATE INDEX ix_objective_goal_id ON objective (goal_id)
""")
    op.execute("""\
CREATE INDEX ix_objective_owner_id ON objective (owner_id)
""")
    op.execute("""\
CREATE INDEX ix_objective_team_id ON objective (team_id)
""")
    op.execute("""\
CREATE INDEX ix_objective_title ON objective (title)
""")
    op.execute("""\
CREATE TABLE alignment_edge (
	id SERIAL NOT NULL, 
	parent_id INTEGER NOT NULL, 
	child_id INTEGER NOT NULL, 
	alignment_type alignmenttype NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_by VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES objective (id), 
	FOREIGN KEY(child_id) REFERENCES objective (id)
)
""")
    op.execute("""\
CREATE INDEX ix_alignment_edge_child_id ON alignment_edge (child_id)
""")
    op.execute("""\
CREATE INDEX ix_alignment_edge_parent_id ON alignment_edge (parent_id)
""")
    op.execute("""\
CREATE UNIQUE INDEX ix_alignment_parent_child ON alignment_edge (parent_id, child_id)
""")
    op.execute("""\
CREATE TABLE key_result (
	title VARCHAR NOT NULL, 
	description VARCHAR, 
	progress INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	owner_id INTEGER, 
	team_id INTEGER, 
	created_by VARCHAR, 
	updated_by VARCHAR, 
	is_expanded BOOLEAN NOT NULL, 
	external_id VARCHAR, 
	deadline TIMESTAMP WITHOUT TIME ZONE, 
	id SERIAL NOT NULL, 
	objective_id INTEGER NOT NULL, 
	start_value FLOAT NOT NULL, 
	target_value FLOAT NOT NULL, 
	current_value FLOAT NOT NULL, 
	unit VARCHAR, 
	metric_type metrictype NOT NULL, 
	initiative_tags VARCHAR, 
	weight FLOAT NOT NULL, 
	ai_analysis VARCHAR, 
	analysis_updated_at TIMESTAMP WITHOUT TIME ZONE, 
	state lifecyclestate NOT NULL, 
	final_reflection VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_key_result_progress_range CHECK (progress >= 0 AND progress <= 100), 
	FOREIGN KEY(owner_id) REFERENCES "user" (id), 
	FOREIGN KEY(team_id) REFERENCES team (id), 
	FOREIGN KEY(objective_id) REFERENCES objective (id)
)
""")
    op.execute("""\
CREATE INDEX ix_key_result_external_id ON key_result (external_id)
""")
    op.execute("""\
CREATE INDEX ix_key_result_objective_id ON key_result (objective_id)
""")
    op.execute("""\
CREATE INDEX ix_key_result_owner_id ON key_result (owner_id)
""")
    op.execute("""\
CREATE INDEX ix_key_result_team_id ON key_result (team_id)
""")
    op.execute("""\
CREATE INDEX ix_key_result_title ON key_result (title)
""")
    op.execute("""\
CREATE TABLE objective_alignment_link (
	id SERIAL NOT NULL, 
	objective_id INTEGER NOT NULL, 
	linked_entity_type VARCHAR NOT NULL, 
	linked_entity_id INTEGER NOT NULL, 
	direction VARCHAR NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_by VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(objective_id) REFERENCES objective (id)
)
""")
    op.execute("""\
CREATE UNIQUE INDEX ix_obj_align_obj_linked ON objective_alignment_link (objective_id, linked_entity_type, linked_entity_id)
""")
    op.execute("""\
CREATE INDEX ix_objective_alignment_link_objective_id ON objective_alignment_link (objective_id)
""")
    op.execute("""\
CREATE TABLE experiment (
	id SERIAL NOT NULL, 
	key_result_id INTEGER NOT NULL, 
	cycle_id INTEGER NOT NULL, 
	created_by VARCHAR NOT NULL, 
	hypothesis VARCHAR NOT NULL, 
	change_description VARCHAR NOT NULL, 
	start_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	end_at TIMESTAMP WITHOUT TIME ZONE, 
	status experimentstatus NOT NULL, 
	decision experimentdecision, 
	decision_rationale VARCHAR, 
	expected_effect_direction expectedeffectdirection, 
	expected_effect_size FLOAT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(key_result_id) REFERENCES key_result (id), 
	FOREIGN KEY(cycle_id) REFERENCES cycle (id)
)
""")
    op.execute("""\
CREATE INDEX ix_experiment_cycle_id ON experiment (cycle_id)
""")
    op.execute("""\
CREATE INDEX ix_experiment_cycle_status ON experiment (cycle_id, status)
""")
    op.execute("""\
CREATE INDEX ix_experiment_key_result_id ON experiment (key_result_id)
""")
    op.execute("""\
CREATE INDEX ix_experiment_kr_status ON experiment (key_result_id, status)
""")
    op.execute("""\
CREATE TABLE task (
	title VARCHAR NOT NULL, 
	description VARCHAR, 
	progress INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	owner_id INTEGER, 
	team_id INTEGER, 
	created_by VARCHAR, 
	updated_by VARCHAR, 
	is_expanded BOOLEAN NOT NULL, 
	external_id VARCHAR, 
	deadline TIMESTAMP WITHOUT TIME ZONE, 
	id SERIAL NOT NULL, 
	key_result_id INTEGER NOT NULL, 
	status taskstatus NOT NULL, 
	start_date TIMESTAMP WITHOUT TIME ZONE, 
	estimated_minutes INTEGER NOT NULL, 
	total_time_spent INTEGER NOT NULL, 
	timer_started_at TIMESTAMP WITHOUT TIME ZONE, 
	assignee_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_task_progress_non_negative CHECK (progress >= 0), 
	CONSTRAINT ck_task_estimated_minutes_non_negative CHECK (estimated_minutes >= 0), 
	CONSTRAINT ck_task_total_time_spent_non_negative CHECK (total_time_spent >= 0), 
	FOREIGN KEY(owner_id) REFERENCES "user" (id), 
	FOREIGN KEY(team_id) REFERENCES team (id), 
	FOREIGN KEY(key_result_id) REFERENCES key_result (id), 
	FOREIGN KEY(assignee_id) REFERENCES "user" (id)
)
""")
    op.execute("""\
CREATE INDEX ix_task_deadline_progress ON task (deadline, progress)
""")
    op.execute("""\
CREATE INDEX ix_task_external_id ON task (external_id)
""")
    op.execute("""\
CREATE INDEX ix_task_key_result_id ON task (key_result_id)
""")
    op.execute("""\
CREATE INDEX ix_task_owner_id ON task (owner_id)
""")
    op.execute("""\
CREATE INDEX ix_task_status_kr ON task (status, key_result_id)
""")
    op.execute("""\
CREATE INDEX ix_task_team_id ON task (team_id)
""")
    op.execute("""\
CREATE INDEX ix_task_timer_started_at ON task (timer_started_at)
""")
    op.execute("""\
CREATE INDEX ix_task_title ON task (title)
""")
    op.execute("""\
CREATE TABLE check_in (
	id SERIAL NOT NULL, 
	key_result_id INTEGER NOT NULL, 
	value FLOAT NOT NULL, 
	confidence_score INTEGER NOT NULL, 
	comment VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	variation_type variationtype, 
	special_cause_note VARCHAR, 
	experiment_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_check_in_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 10), 
	FOREIGN KEY(key_result_id) REFERENCES key_result (id), 
	FOREIGN KEY(experiment_id) REFERENCES experiment (id)
)
""")
    op.execute("""\
CREATE INDEX ix_check_in_key_result_id ON check_in (key_result_id)
""")
    op.execute("""\
CREATE INDEX ix_check_in_kr_created ON check_in (key_result_id, created_at)
""")
    op.execute("""\
CREATE INDEX ix_check_in_kr_var_created ON check_in (key_result_id, variation_type, created_at)
""")
    op.execute("""\
CREATE TABLE retro_experiment_outcome (
	id SERIAL NOT NULL, 
	retrospective_id INTEGER NOT NULL, 
	experiment_id INTEGER NOT NULL, 
	decision experimentdecision NOT NULL, 
	rationale VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(retrospective_id) REFERENCES retrospective (id), 
	FOREIGN KEY(experiment_id) REFERENCES experiment (id)
)
""")
    op.execute("""\
CREATE INDEX ix_retro_experiment_outcome_experiment_id ON retro_experiment_outcome (experiment_id)
""")
    op.execute("""\
CREATE INDEX ix_retro_experiment_outcome_retrospective_id ON retro_experiment_outcome (retrospective_id)
""")
    op.execute("""\
CREATE UNIQUE INDEX ux_retro_experiment ON retro_experiment_outcome (retrospective_id, experiment_id)
""")
    op.execute("""\
CREATE TABLE work_log (
	id SERIAL NOT NULL, 
	task_id INTEGER NOT NULL, 
	start_time TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	end_time TIMESTAMP WITHOUT TIME ZONE, 
	duration_minutes FLOAT NOT NULL, 
	note VARCHAR, 
	summary VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_work_log_duration_non_negative CHECK (duration_minutes >= 0), 
	FOREIGN KEY(task_id) REFERENCES task (id)
)
""")
    op.execute("""\
CREATE INDEX ix_work_log_start_time ON work_log (start_time)
""")
    op.execute("""\
CREATE INDEX ix_work_log_task_id ON work_log (task_id)
""")
    op.execute("""\
CREATE INDEX ix_work_log_task_start ON work_log (task_id, start_time)
""")
    op.execute("""\
CREATE UNIQUE INDEX ux_work_log_task_open ON work_log (task_id) WHERE end_time IS NULL
""")


    # Enable RLS on all user-data tables (Supabase hardening), matching the
    # behavior of the previously squashed enable_rls migration.
    for table in sorted(_all_tables() - _RLS_EXCLUDED):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    if not _is_postgres():
        return
    bind = op.get_bind()
    tables = [t for t in reversed(_table_names())]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
