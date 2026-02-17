"""add lifecycle states

Revision ID: de90d7933d38
Revises: l2f3a4b5c6d8
Create Date: 2026-02-17 18:38:18.619819

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'de90d7933d38'
down_revision: Union[str, Sequence[str], None] = 'l2f3a4b5c6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    
    if dialect == 'postgresql':
        # 1. Create enum types explicitly for Postgres
        sa.Enum('DRAFT', 'ACTIVE', 'GRADING', 'ARCHIVED', name='lifecyclestate').create(bind, checkfirst=True)
        sa.Enum('BOOLEAN', 'NUMERIC', 'PERCENT', name='metrictype').create(bind, checkfirst=True)
        sa.Enum('UNWEIGHTED', 'WEIGHTED', name='scoremode').create(bind, checkfirst=True)

        # 2. Backfill existing NULLs to avoid constraint errors
        op.execute("UPDATE key_result SET weight = 1.0 WHERE weight IS NULL")
        op.execute("UPDATE key_result SET start_value = 0.0 WHERE start_value IS NULL")
        op.execute("UPDATE objective SET weight = 1.0 WHERE weight IS NULL")
        
        # 3. Drop old defaults
        op.execute("ALTER TABLE key_result ALTER COLUMN metric_type DROP DEFAULT")
        op.execute("ALTER TABLE objective ALTER COLUMN score_mode DROP DEFAULT")

        # 4. Alter types with robust casting
        op.execute("ALTER TABLE key_result ALTER COLUMN metric_type TYPE metrictype USING CASE WHEN upper(metric_type) IN ('BOOLEAN', 'NUMERIC', 'PERCENT') THEN upper(metric_type)::metrictype ELSE 'NUMERIC'::metrictype END")
        op.execute("ALTER TABLE objective ALTER COLUMN score_mode TYPE scoremode USING CASE WHEN upper(score_mode) IN ('UNWEIGHTED', 'WEIGHTED') THEN upper(score_mode)::scoremode ELSE 'UNWEIGHTED'::scoremode END")

        # 5. Set new defaults and not null constraints
        op.execute("ALTER TABLE key_result ALTER COLUMN metric_type SET DEFAULT 'NUMERIC'::metrictype")
        op.execute("ALTER TABLE key_result ALTER COLUMN metric_type SET NOT NULL")
        op.execute("ALTER TABLE objective ALTER COLUMN score_mode SET DEFAULT 'UNWEIGHTED'::scoremode")
        op.execute("ALTER TABLE objective ALTER COLUMN score_mode SET NOT NULL")

        # 6. Remaining columns for Postgres
        with op.batch_alter_table('key_result', schema=None) as batch_op:
            batch_op.add_column(sa.Column('state', sa.Enum('DRAFT', 'ACTIVE', 'GRADING', 'ARCHIVED', name='lifecyclestate'), nullable=False, server_default='DRAFT'))
            batch_op.add_column(sa.Column('final_reflection', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
            batch_op.alter_column('start_value', nullable=False)
            batch_op.alter_column('weight', nullable=False, server_default='1.0')

        with op.batch_alter_table('objective', schema=None) as batch_op:
            batch_op.add_column(sa.Column('state', sa.Enum('DRAFT', 'ACTIVE', 'GRADING', 'ARCHIVED', name='lifecyclestate'), nullable=False, server_default='DRAFT'))
            batch_op.add_column(sa.Column('final_reflection', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
            batch_op.alter_column('weight', nullable=False, server_default='1.0')
    else:
        # Standard Alembic behavior for SQLite/others
        inspector = sa.inspect(bind)
        existing_tables = set(inspector.get_table_names())
        
        # 1. Handle KeyResult alterations
        if 'key_result' in existing_tables:
            kr_cols = {c['name'] for c in inspector.get_columns('key_result')}
            if 'state' not in kr_cols:
                op.add_column('key_result', sa.Column('state', sa.Enum('DRAFT', 'ACTIVE', 'GRADING', 'ARCHIVED', name='lifecyclestate'), nullable=False, server_default='DRAFT'))
            if 'final_reflection' not in kr_cols:
                op.add_column('key_result', sa.Column('final_reflection', sa.String(), nullable=True))

            with op.batch_alter_table('key_result', schema=None) as batch_op:
                batch_op.alter_column('metric_type',
                       type_=sa.Enum('BOOLEAN', 'NUMERIC', 'PERCENT', name='metrictype'),
                       nullable=False,
                       server_default='NUMERIC')
                batch_op.alter_column('start_value', nullable=False)
                batch_op.alter_column('weight', nullable=False, server_default='1.0')

        # 2. Handle Objective alterations
        if 'objective' in existing_tables:
            obj_cols = {c['name'] for c in inspector.get_columns('objective')}
            if 'state' not in obj_cols:
                op.add_column('objective', sa.Column('state', sa.Enum('DRAFT', 'ACTIVE', 'GRADING', 'ARCHIVED', name='lifecyclestate'), nullable=False, server_default='DRAFT'))
            if 'final_reflection' not in obj_cols:
                op.add_column('objective', sa.Column('final_reflection', sa.String(), nullable=True))

            with op.batch_alter_table('objective', schema=None) as batch_op:
                batch_op.alter_column('score_mode',
                       type_=sa.Enum('UNWEIGHTED', 'WEIGHTED', name='scoremode'),
                       nullable=False,
                       server_default='UNWEIGHTED')
                batch_op.alter_column('weight', nullable=False, server_default='1.0')


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    
    if dialect == 'postgresql':
        # Revert Raw SQL changes
        op.execute("ALTER TABLE key_result ALTER COLUMN metric_type TYPE varchar USING metric_type::text")
        op.execute("ALTER TABLE key_result ALTER COLUMN metric_type SET DEFAULT 'numeric'::varchar")
        op.execute("ALTER TABLE objective ALTER COLUMN score_mode TYPE varchar USING score_mode::text")
        op.execute("ALTER TABLE objective ALTER COLUMN score_mode SET DEFAULT 'unweighted'::varchar")
    
    with op.batch_alter_table('objective', schema=None) as batch_op:
        batch_op.drop_column('final_reflection')
        batch_op.drop_column('state')
        batch_op.alter_column('weight', nullable=True)

    with op.batch_alter_table('key_result', schema=None) as batch_op:
        batch_op.drop_column('final_reflection')
        batch_op.drop_column('state')
        batch_op.alter_column('weight', nullable=True)
        batch_op.alter_column('start_value', nullable=True)
