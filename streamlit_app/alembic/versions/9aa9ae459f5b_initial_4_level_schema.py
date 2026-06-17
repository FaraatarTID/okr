"""Initial schema bootstrap (hard cutover baseline).

Revision ID: 9aa9ae459f5b
Revises:
Create Date: 2026-02-03 10:32:27.101974
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
from sqlmodel import SQLModel


# revision identifiers, used by Alembic.
revision: str = "9aa9ae459f5b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the current baseline schema when tables are missing.

    This migration is intentionally deterministic and SQLite-safe:
    it never runs legacy ALTER/DROP steps from pre-cutover history.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    baseline_tables = {
        "user",
        "cycle",
        "goal",
        "objective",
        "key_result",
        "task",
        "work_log",
        "check_in",
        "weekly_plan",
        "retrospective",
        "sync_retry_event",
        "auth_throttle_state",
    }

    if baseline_tables.issubset(existing_tables):
        return

    # Import registers all SQLModel tables, then create what is missing.
    import src.models  # noqa: F401

    SQLModel.metadata.create_all(bind)


def downgrade() -> None:
    """Downgrade is intentionally unsupported after hard cutover baseline."""
    return
