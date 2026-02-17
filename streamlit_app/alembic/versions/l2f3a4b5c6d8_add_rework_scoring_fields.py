"""add_rework_scoring_fields

Revision ID: l2f3a4b5c6d8
Revises: k1e2f3a4b5c6
Create Date: 2026-02-17 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'l2f3a4b5c6d8'
down_revision = 'k1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Update Objective table
    if 'objective' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('objective')}
        with op.batch_alter_table('objective', schema=None) as batch_op:
            if 'score_mode' not in existing_cols:
                # Default to 'unweighted' to match existing behavior
                batch_op.add_column(sa.Column('score_mode', sa.String(), nullable=True, server_default='unweighted'))
    
    # 2. Update KeyResult table
    if 'key_result' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('key_result')}
        with op.batch_alter_table('key_result', schema=None) as batch_op:
            if 'start_value' not in existing_cols:
                batch_op.add_column(sa.Column('start_value', sa.Float(), nullable=True, server_default='0.0'))
            
            if 'target_value' not in existing_cols:
                batch_op.add_column(sa.Column('target_value', sa.Float(), nullable=True, server_default='100.0'))
            
            if 'current_value' not in existing_cols:
                batch_op.add_column(sa.Column('current_value', sa.Float(), nullable=True, server_default='0.0'))
            
            if 'metric_type' not in existing_cols:
                batch_op.add_column(sa.Column('metric_type', sa.String(), nullable=True, server_default='numeric'))
            
            if 'unit' not in existing_cols:
                batch_op.add_column(sa.Column('unit', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('key_result', schema=None) as batch_op:
        batch_op.drop_column('unit')
        batch_op.drop_column('metric_type')
        batch_op.drop_column('current_value')
        batch_op.drop_column('target_value')
        batch_op.drop_column('start_value')

    with op.batch_alter_table('objective', schema=None) as batch_op:
        batch_op.drop_column('score_mode')
