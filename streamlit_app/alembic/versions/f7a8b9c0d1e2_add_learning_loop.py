"""add learning loop tables and check_in extensions

Revision ID: f7a8b9c0d1e2
Revises: e44e99596342
Create Date: 2026-02-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e44e99596342'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Create experiment table
    if 'experiment' not in existing_tables:
        op.create_table(
            'experiment',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('key_result_id', sa.Integer(), nullable=False),
            sa.Column('cycle_id', sa.Integer(), nullable=False),
            sa.Column('created_by', sa.String(), nullable=False),
            sa.Column('hypothesis', sa.String(), nullable=False),
            sa.Column('change_description', sa.String(), nullable=False),
            sa.Column('start_at', sa.DateTime(), nullable=False),
            sa.Column('end_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(), nullable=False, server_default='PLANNED'),
            sa.Column('decision', sa.String(), nullable=True),
            sa.Column('decision_rationale', sa.String(), nullable=True),
            sa.Column('expected_effect_direction', sa.String(), nullable=True),
            sa.Column('expected_effect_size', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['key_result_id'], ['key_result.id'], ),
            sa.ForeignKeyConstraint(['cycle_id'], ['cycle.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('experiment', schema=None) as batch_op:
            batch_op.create_index('ix_experiment_key_result_id', ['key_result_id'], unique=False)
            batch_op.create_index('ix_experiment_cycle_id', ['cycle_id'], unique=False)
            batch_op.create_index('ix_experiment_kr_status', ['key_result_id', 'status'], unique=False)
            batch_op.create_index('ix_experiment_cycle_status', ['cycle_id', 'status'], unique=False)

    # Create retro_experiment_outcome table
    if 'retro_experiment_outcome' not in existing_tables:
        op.create_table(
            'retro_experiment_outcome',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('retrospective_id', sa.Integer(), nullable=False),
            sa.Column('experiment_id', sa.Integer(), nullable=False),
            sa.Column('decision', sa.String(), nullable=False),
            sa.Column('rationale', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['retrospective_id'], ['retrospective.id'], ),
            sa.ForeignKeyConstraint(['experiment_id'], ['experiment.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('retro_experiment_outcome', schema=None) as batch_op:
            batch_op.create_index('ix_retro_experiment_outcome_retrospective_id', ['retrospective_id'], unique=False)
            batch_op.create_index('ix_retro_experiment_outcome_experiment_id', ['experiment_id'], unique=False)
            batch_op.create_index('ux_retro_experiment', ['retrospective_id', 'experiment_id'], unique=True)

    # Add learning loop columns/index to check_in table when present.
    # Some upgrade paths stamp forward from legacy snapshots where check_in is absent.
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if 'check_in' in existing_tables:
        check_in_columns = {col['name'] for col in inspector.get_columns('check_in')}
        check_in_indexes = {
            idx.get('name') for idx in inspector.get_indexes('check_in') if idx.get('name')
        }

        with op.batch_alter_table('check_in', schema=None) as batch_op:
            if 'variation_type' not in check_in_columns:
                batch_op.add_column(sa.Column('variation_type', sa.String(), nullable=True))
            if 'special_cause_note' not in check_in_columns:
                batch_op.add_column(sa.Column('special_cause_note', sa.String(), nullable=True))
            if 'experiment_id' not in check_in_columns:
                batch_op.add_column(sa.Column('experiment_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_check_in_experiment', 'experiment', ['experiment_id'], ['id']
                )
            if 'ix_check_in_kr_var_created' not in check_in_indexes:
                batch_op.create_index(
                    'ix_check_in_kr_var_created',
                    ['key_result_id', 'variation_type', 'created_at'],
                    unique=False,
                )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove check_in extensions
    with op.batch_alter_table('check_in', schema=None) as batch_op:
        try:
            batch_op.drop_index('ix_check_in_kr_var_created')
        except Exception:
            pass
        try:
            batch_op.drop_constraint('fk_check_in_experiment', type_='foreignkey')
        except Exception:
            pass
        try:
            batch_op.drop_column('experiment_id')
        except Exception:
            pass
        try:
            batch_op.drop_column('special_cause_note')
        except Exception:
            pass
        try:
            batch_op.drop_column('variation_type')
        except Exception:
            pass

    # Drop retro_experiment_outcome table
    op.drop_table('retro_experiment_outcome')

    # Drop experiment table
    op.drop_table('experiment')
