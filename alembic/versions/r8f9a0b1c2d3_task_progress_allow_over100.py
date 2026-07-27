"""Allow task progress to exceed 100 (auto-computed from time spent).

Revision ID: r8f9a0b1c2d3
Revises: q7e8f9a0b1c2
Create Date: 2026-06-15 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "r8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "q7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _check_constraint_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return {
            c["name"]
            for c in inspector.get_check_constraints(table_name)
            if c.get("name")
        }
    except Exception:
        return set()


def _has_table(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("task"):
        return
    existing = _check_constraint_names("task")
    if "ck_task_progress_range" in existing:
        with op.batch_alter_table("task") as batch_op:
            batch_op.drop_constraint("ck_task_progress_range", type_="check")
    with op.batch_alter_table("task") as batch_op:
        batch_op.create_check_constraint(
            "ck_task_progress_non_negative",
            "progress >= 0",
        )


def downgrade() -> None:
    if not _has_table("task"):
        return
    existing = _check_constraint_names("task")
    if "ck_task_progress_non_negative" in existing:
        with op.batch_alter_table("task") as batch_op:
            batch_op.drop_constraint("ck_task_progress_non_negative", type_="check")
    with op.batch_alter_table("task") as batch_op:
        batch_op.create_check_constraint(
            "ck_task_progress_range",
            "progress >= 0 AND progress <= 100",
        )
