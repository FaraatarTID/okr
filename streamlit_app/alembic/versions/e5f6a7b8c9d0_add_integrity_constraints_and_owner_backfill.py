"""Add integrity constraints and goal owner backfill.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-13 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    try:
        return table_name in _inspector().get_table_names()
    except Exception:
        return False


def _column_names(table_name: str) -> set:
    try:
        return {col["name"] for col in _inspector().get_columns(table_name)}
    except Exception:
        return set()


def _index_names(table_name: str) -> set:
    try:
        return {idx["name"] for idx in _inspector().get_indexes(table_name)}
    except Exception:
        return set()


def _check_constraint_names(table_name: str) -> set:
    try:
        names = set()
        for ck in _inspector().get_check_constraints(table_name):
            name = ck.get("name")
            if name:
                names.add(name)
        return names
    except Exception:
        return set()


def _fk_names_for_column(table_name: str, column_name: str) -> set:
    try:
        names = set()
        for fk in _inspector().get_foreign_keys(table_name):
            constrained_cols = fk.get("constrained_columns") or []
            if column_name in constrained_cols:
                fk_name = fk.get("name")
                if fk_name:
                    names.add(fk_name)
        return names
    except Exception:
        return set()


def _has_fk_for_column(table_name: str, column_name: str) -> bool:
    try:
        for fk in _inspector().get_foreign_keys(table_name):
            constrained_cols = fk.get("constrained_columns") or []
            if column_name in constrained_cols:
                return True
        return False
    except Exception:
        return False


def _ensure_check_constraint(table_name: str, name: str, condition: str) -> None:
    if not _has_table(table_name):
        return
    if name in _check_constraint_names(table_name):
        return
    try:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_check_constraint(name, condition)
    except Exception:
        # Legacy SQLite installs may contain orphaned FK metadata
        # (e.g., task -> initiative) that makes reflection fail during batch ops.
        # Skip best-effort check creation in that case so the migration can continue.
        return


def _drop_check_constraint_if_exists(table_name: str, name: str) -> None:
    if not _has_table(table_name):
        return
    if name not in _check_constraint_names(table_name):
        return
    try:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(name, type_="check")
    except Exception:
        return


def upgrade() -> None:
    if _has_table("goal"):
        goal_columns = _column_names("goal")

        # Ensure normalized owner FK column exists.
        if "owner_id" not in goal_columns:
            with op.batch_alter_table("goal") as batch_op:
                batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
            goal_columns = _column_names("goal")

        # Keep lookup efficient for owner scoped reads.
        if {"owner_id", "cycle_id"}.issubset(goal_columns):
            if "ix_goal_owner_cycle" not in _index_names("goal"):
                op.create_index("ix_goal_owner_cycle", "goal", ["owner_id", "cycle_id"], unique=False)

        # Repair invalid owner links and backfill from legacy username ownership.
        if _has_table("user") and "owner_id" in goal_columns:
            op.execute(
                """
                UPDATE "goal"
                SET owner_id = NULL
                WHERE owner_id IS NOT NULL
                  AND owner_id NOT IN (SELECT id FROM "user")
                """
            )
            op.execute(
                """
                UPDATE "goal"
                SET owner_id = (
                    SELECT u.id
                    FROM "user" AS u
                    WHERE u.username = "goal".user_id
                    LIMIT 1
                )
                WHERE owner_id IS NULL
                  AND user_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1
                      FROM "user" AS ux
                      WHERE ux.username = "goal".user_id
                  )
                """
            )

            # Add FK if it is not already enforced.
            if not _has_fk_for_column("goal", "owner_id"):
                with op.batch_alter_table("goal") as batch_op:
                    batch_op.create_foreign_key(
                        "fk_goal_owner_id_user",
                        "user",
                        ["owner_id"],
                        ["id"],
                    )

    _ensure_check_constraint("goal", "ck_goal_progress_range", "progress >= 0 AND progress <= 100")
    _ensure_check_constraint("objective", "ck_objective_progress_range", "progress >= 0 AND progress <= 100")
    _ensure_check_constraint("key_result", "ck_key_result_progress_range", "progress >= 0 AND progress <= 100")
    _ensure_check_constraint("task", "ck_task_progress_range", "progress >= 0 AND progress <= 100")
    _ensure_check_constraint("task", "ck_task_estimated_minutes_non_negative", "estimated_minutes >= 0")
    _ensure_check_constraint("task", "ck_task_total_time_spent_non_negative", "total_time_spent >= 0")
    _ensure_check_constraint("work_log", "ck_work_log_duration_non_negative", "duration_minutes >= 0")
    _ensure_check_constraint(
        "check_in",
        "ck_check_in_confidence_range",
        "confidence_score >= 0 AND confidence_score <= 10",
    )


def downgrade() -> None:
    _drop_check_constraint_if_exists("check_in", "ck_check_in_confidence_range")
    _drop_check_constraint_if_exists("work_log", "ck_work_log_duration_non_negative")
    _drop_check_constraint_if_exists("task", "ck_task_total_time_spent_non_negative")
    _drop_check_constraint_if_exists("task", "ck_task_estimated_minutes_non_negative")
    _drop_check_constraint_if_exists("task", "ck_task_progress_range")
    _drop_check_constraint_if_exists("key_result", "ck_key_result_progress_range")
    _drop_check_constraint_if_exists("objective", "ck_objective_progress_range")
    _drop_check_constraint_if_exists("goal", "ck_goal_progress_range")

    if not _has_table("goal"):
        return

    goal_columns = _column_names("goal")
    if "owner_id" not in goal_columns:
        return

    for fk_name in _fk_names_for_column("goal", "owner_id"):
        with op.batch_alter_table("goal") as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")

    if "ix_goal_owner_cycle" in _index_names("goal"):
        op.drop_index("ix_goal_owner_cycle", table_name="goal")

    with op.batch_alter_table("goal") as batch_op:
        batch_op.drop_column("owner_id")
