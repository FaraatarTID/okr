"""add alignment edge

Revision ID: e44e99596342
Revises: de90d7933d38
Create Date: 2026-02-17 19:30:07.673783

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e44e99596342'
down_revision: Union[str, Sequence[str], None] = 'de90d7933d38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'alignment_edge' not in existing_tables:
        op.create_table(
            'alignment_edge',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('parent_id', sa.Integer(), nullable=False),
            sa.Column('child_id', sa.Integer(), nullable=False),
            sa.Column('alignment_type', sa.String(), nullable=False, server_default='SUPPORTS'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.String(), nullable=True),
            sa.ForeignKeyConstraint(['child_id'], ['objective.id'], ),
            sa.ForeignKeyConstraint(['parent_id'], ['objective.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        # Handle batch independently if needed, though op.create_table takes indexes.
        # But established style uses batch_alter_table for indexes.
        with op.batch_alter_table('alignment_edge', schema=None) as batch_op:
            batch_op.create_index('ix_alignment_edge_child_id', ['child_id'], unique=False)
            batch_op.create_index('ix_alignment_edge_parent_id', ['parent_id'], unique=False)
            batch_op.create_index('ix_alignment_parent_child', ['parent_id', 'child_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('alignment_edge')
