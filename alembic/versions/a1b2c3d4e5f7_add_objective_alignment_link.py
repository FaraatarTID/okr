"""add objective alignment link

Revision ID: a1b2c3d4e5f7
Revises: t0b1c2d3e4f5
Create Date: 2026-07-22 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "t0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "objective_alignment_link" not in existing_tables:
        op.create_table(
            "objective_alignment_link",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("objective_id", sa.Integer(), nullable=False),
            sa.Column("linked_entity_type", sa.String(), nullable=False),
            sa.Column("linked_entity_id", sa.Integer(), nullable=False),
            sa.Column("direction", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.ForeignKeyConstraint(
                ["objective_id"],
                ["objective.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("objective_alignment_link", schema=None) as batch_op:
            batch_op.create_index(
                "ix_obj_align_objective_id", ["objective_id"], unique=False
            )
            batch_op.create_index(
                "ix_obj_align_obj_linked",
                ["objective_id", "linked_entity_type", "linked_entity_id"],
                unique=True,
            )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("objective_alignment_link")
