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

# Historical destructive cleanup.  It is not eligible for an unattended
# production-fleet rollout; the approved maintenance record is retained below.
MIGRATION_METADATA = {
    "additive": False,
    "backfill": False,
    "contract": True,
    "destructive": True,
    "locking_risk": True,
    "reversible": False,
    "compatible_with_previous_release": False,
    "maintenance_window_only": True,
    "exception_record": "drop_global_cycle_index.json",
}


def upgrade() -> None:
    # Older databases may still retain this index after the migration squash.
    # PostgreSQL forbids CONCURRENTLY inside the normal Alembic transaction.
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("DROP INDEX CONCURRENTLY IF EXISTS ux_cycle_single_active")
        return
    op.execute("DROP INDEX IF EXISTS ux_cycle_single_active")


def downgrade() -> None:
    # The former global policy is intentionally not restored. Reintroducing it
    # would conflict with the per-owner active-cycle model.
    pass
