"""enable_rls_on_all_tables

Revision ID: 7f1e28f4cc6f
Revises: r8f9a0b1c2d3
Create Date: 2026-07-01 15:25:30.222575

"""

from typing import Sequence, Union

from alembic import op


from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "7f1e28f4cc6f"
down_revision: Union[str, Sequence[str], None] = "r8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    inspector = inspect(op.get_bind())
    try:
        return set(inspector.get_table_names())
    except Exception:
        return set()


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        existing_tables = _table_names()
        tables = [
            "audit_event",
            "alignment_edge",
            "experiment",
            "retro_experiment_outcome",
            "alembic_version",
            "user",
            "auth_throttle_state",
            "goal",
            "cycle",
            "weekly_plan",
            "objective",
            "retrospective",
            "check_in",
            "task",
            "work_log",
            "async_job",
            "team",
            "key_result",
        ]
        for table in tables:
            if table in existing_tables:
                op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        existing_tables = _table_names()
        tables = [
            "audit_event",
            "alignment_edge",
            "experiment",
            "retro_experiment_outcome",
            "alembic_version",
            "user",
            "auth_throttle_state",
            "goal",
            "cycle",
            "weekly_plan",
            "objective",
            "retrospective",
            "check_in",
            "task",
            "work_log",
            "async_job",
            "team",
            "key_result",
        ]
        for table in tables:
            if table in existing_tables:
                op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
