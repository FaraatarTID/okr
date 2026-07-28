"""Merge split Alembic heads produced by independent evolution paths.

The migration graph currently has two active terminal revisions:
``bc1d2e3f4a5b`` (operations/performance branch) and ``u1c2d3e4f5a6``
(token-version branch). This merge keeps the schema history linear for CI checks
that still upgrade to ``head``.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "x1f2e3d4c5b6a"
down_revision = ("bc1d2e3f4a5b", "u1c2d3e4f5a6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op merge revision."""
    op.execute("PRAGMA user_version = user_version")  # no-op for deterministic SQL history.


def downgrade() -> None:
    """No-op downgrade for merge revision."""
    op.execute("PRAGMA user_version = user_version")  # no-op for deterministic SQL history.
