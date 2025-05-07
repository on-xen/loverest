"""Change telegram_id to BigInteger

Revision ID: bigint_telegram_id
Revises: add_donations
Create Date: 2024-05-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bigint_telegram_id'
down_revision: Union[str, None] = 'add_donations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # PostgreSQL может изменить тип данных без удаления данных и переиндексации
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('telegram_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)

def downgrade() -> None:
    # Обратное изменение может привести к потере данных, если ID больше максимального Integer
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('telegram_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True) 