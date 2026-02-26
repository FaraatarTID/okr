"""Add unique partial index for one open work log per task.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-13 13:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set:
    inspector = inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    # Heal legacy duplicates first so unique index creation is safe.
    op.execute(
        """
        UPDATE work_log
        SET end_time = start_time,
            duration_minutes = 0
        WHERE end_time IS NULL
          AND EXISTS (
              SELECT 1
              FROM work_log newer
              WHERE newer.task_id = work_log.task_id
                AND newer.end_time IS NULL
                AND newer.id > work_log.id
          )
        """
    )

    existing = _index_names("work_log")
    if "ux_work_log_task_open" not in existing:
        op.create_index(
            "ux_work_log_task_open",
            "work_log",
            ["task_id"],
            unique=True,
            sqlite_where=sa.text("end_time IS NULL"),
            postgresql_where=sa.text("end_time IS NULL"),
        )


def downgrade() -> None:
    existing = _index_names("work_log")
    if "ux_work_log_task_open" in existing:
        op.drop_index("ux_work_log_task_open", table_name="work_log")
