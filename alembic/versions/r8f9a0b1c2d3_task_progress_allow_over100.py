"""Allow task progress to exceed 100 (auto-computed from time spent).

Revision ID: r8f9a0b1c2d3
Revises: q7e8f9a0b1c2
Create Date: 2026-06-15 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "r8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "q7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    constraints = [
        c["name"]
        for c in inspector.get_check_constraints("task")
        if c.get("name")
    ]
    if "ck_task_progress_range" in constraints:
        op.drop_constraint("ck_task_progress_range", "task", type_="check")
    op.create_check_constraint(
        "ck_task_progress_non_negative",
        "task",
        "progress >= 0",
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    constraints = [
        c["name"]
        for c in inspector.get_check_constraints("task")
        if c.get("name")
    ]
    if "ck_task_progress_non_negative" in constraints:
        op.drop_constraint("ck_task_progress_non_negative", "task", type_="check")
    op.create_check_constraint(
        "ck_task_progress_range",
        "task",
        "progress >= 0 AND progress <= 100",
    )
