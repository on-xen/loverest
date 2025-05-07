"""Initial migration

Revision ID: initial_migration
Revises: 
Create Date: 2024-03-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'initial_migration'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=False),
        sa.Column('is_restaurant_owner', sa.Boolean(), nullable=False, default=False),
        sa.Column('current_restaurant_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )

    # Create restaurants table
    op.create_table(
        'restaurants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('invite_code', sa.String(10), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.UniqueConstraint('invite_code'),
        sa.UniqueConstraint('owner_id')
    )

    # Create menu_items table
    op.create_table(
        'menu_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(20), nullable=False),
        sa.Column('photo', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('price_kisses', sa.Integer(), nullable=True),
        sa.Column('price_hugs', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'])
    )

    # Add foreign key for current_restaurant_id in users table
    op.create_foreign_key(
        'fk_users_current_restaurant',
        'users', 'restaurants',
        ['current_restaurant_id'], ['id']
    )

def downgrade() -> None:
    # Drop foreign key for current_restaurant_id in users table
    op.drop_constraint('fk_users_current_restaurant', 'users', type_='foreignkey')
    
    # Drop tables in reverse order
    op.drop_table('menu_items')
    op.drop_table('restaurants')
    op.drop_table('users') 