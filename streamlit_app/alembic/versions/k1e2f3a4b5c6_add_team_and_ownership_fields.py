"""add_team_and_ownership_fields

Revision ID: k1e2f3a4b5c6
Revises: j0d1e2f3a4b5
Create Date: 2026-02-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'k1e2f3a4b5c6'
down_revision = 'j0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create Team table if not exists
    if 'team' not in existing_tables:
        op.create_table('team',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_team_name'), 'team', ['name'], unique=True)

    # 2. Add team_id to User
    if 'user' in existing_tables:
        existing_user_cols = {c['name'] for c in inspector.get_columns('user')}
        if 'team_id' not in existing_user_cols:
            with op.batch_alter_table('user', schema=None) as batch_op:
                batch_op.add_column(sa.Column('team_id', sa.Integer(), nullable=True))
                batch_op.create_index(batch_op.f('ix_user_team_id'), ['team_id'], unique=False)
                batch_op.create_foreign_key('fk_user_team', 'team', ['team_id'], ['id'])

    # 3. Add ownership/audit fields to Goal, Objective, KeyResult, Task
    tables = ['goal', 'objective', 'key_result', 'task']
    
    for table in tables:
        if table in existing_tables:
            existing_cols = {c['name'] for c in inspector.get_columns(table)}
            with op.batch_alter_table(table, schema=None) as batch_op:
                # Add common audit fields if missing
                if 'team_id' not in existing_cols:
                    batch_op.add_column(sa.Column('team_id', sa.Integer(), nullable=True))
                    batch_op.create_index(batch_op.f(f'ix_{table}_team_id'), ['team_id'], unique=False)
                    batch_op.create_foreign_key(f'fk_{table}_team', 'team', ['team_id'], ['id'])

                if 'created_by' not in existing_cols:
                    batch_op.add_column(sa.Column('created_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
                
                if 'updated_by' not in existing_cols:
                    batch_op.add_column(sa.Column('updated_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
                
                if table in ['objective', 'key_result'] and 'weight' not in existing_cols:
                    batch_op.add_column(sa.Column('weight', sa.Float(), nullable=True))

                # Add owner_id to everyone EXCEPT Goal (which already has it) if missing
                if table != 'goal' and 'owner_id' not in existing_cols:
                    batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
                    batch_op.create_index(batch_op.f(f'ix_{table}_owner_id'), ['owner_id'], unique=False)
                    batch_op.create_foreign_key(f'fk_{table}_owner', 'user', ['owner_id'], ['id'])


def downgrade() -> None:
    tables = ['goal', 'objective', 'key_result', 'task']
    for table in tables:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_team', type_='foreignkey')
            batch_op.drop_index(batch_op.f(f'ix_{table}_team_id'))
            batch_op.drop_column('updated_by')
            batch_op.drop_column('created_by')
            batch_op.drop_column('team_id')
            
            if table in ['objective', 'key_result']:
                batch_op.drop_column('weight')
            
            if table != 'goal':
                batch_op.drop_constraint(f'fk_{table}_owner', type_='foreignkey')
                batch_op.drop_index(batch_op.f(f'ix_{table}_owner_id'))
                batch_op.drop_column('owner_id')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_team', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_user_team_id'))
        batch_op.drop_column('team_id')

    op.drop_index(op.f('ix_team_name'), table_name='team')
    op.drop_table('team')
