"""Add performance indexes for analytics and timeline queries.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-13 16:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    existing_check_in = _index_names("check_in")
    existing_task = _index_names("task")
    existing_work_log = _index_names("work_log")

    if "ix_check_in_kr_created" not in existing_check_in:
        op.create_index("ix_check_in_kr_created", "check_in", ["key_result_id", "created_at"], unique=False)

    if "ix_task_timer_started_at" not in existing_task:
        op.create_index("ix_task_timer_started_at", "task", ["timer_started_at"], unique=False)
    if "ix_task_deadline_progress" not in existing_task:
        op.create_index("ix_task_deadline_progress", "task", ["deadline", "progress"], unique=False)

    if "ix_work_log_task_start" not in existing_work_log:
        op.create_index("ix_work_log_task_start", "work_log", ["task_id", "start_time"], unique=False)
    if "ix_work_log_start_time" not in existing_work_log:
        op.create_index("ix_work_log_start_time", "work_log", ["start_time"], unique=False)


def downgrade() -> None:
    existing_check_in = _index_names("check_in")
    existing_task = _index_names("task")
    existing_work_log = _index_names("work_log")

    if "ix_work_log_start_time" in existing_work_log:
        op.drop_index("ix_work_log_start_time", table_name="work_log")
    if "ix_work_log_task_start" in existing_work_log:
        op.drop_index("ix_work_log_task_start", table_name="work_log")

    if "ix_task_deadline_progress" in existing_task:
        op.drop_index("ix_task_deadline_progress", table_name="task")
    if "ix_task_timer_started_at" in existing_task:
        op.drop_index("ix_task_timer_started_at", table_name="task")

    if "ix_check_in_kr_created" in existing_check_in:
        op.drop_index("ix_check_in_kr_created", table_name="check_in")
