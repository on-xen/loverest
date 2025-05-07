"""Add donations table and timestamps

Revision ID: add_donations
Revises: initial_migration
Create Date: 2024-03-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_donations'
down_revision: Union[str, None] = 'initial_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Добавляем timestamp поля в существующие таблицы
    op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_activity', sa.DateTime(), nullable=True))
    op.add_column('restaurants', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('menu_items', sa.Column('created_at', sa.DateTime(), nullable=True))
    
    # Создаем таблицу пожертвований
    op.create_table(
        'donations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    # Удаляем таблицу пожертвований
    op.drop_table('donations')
    
    # Удаляем добавленные поля из существующих таблиц
    op.drop_column('menu_items', 'created_at')
    op.drop_column('restaurants', 'created_at')
    op.drop_column('users', 'last_activity')
    op.drop_column('users', 'created_at') 