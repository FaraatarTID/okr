"""Remove the obsolete global active-cycle uniqueness policy.

Revision ID: drop_global_cycle_index
Revises: baseline_2026_08_26
"""

from typing import Sequence, Union

from alembic import op


revision: str = "drop_global_cycle_index"
down_revision: Union[str, Sequence[str], None] = "baseline_2026_08_26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Older databases may still retain this index after the migration squash.
    op.execute("DROP INDEX IF EXISTS ux_cycle_single_active")


def downgrade() -> None:
    # The former global policy is intentionally not restored. Reintroducing it
    # would conflict with the per-owner active-cycle model.
    pass
