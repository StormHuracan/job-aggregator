"""merge heads

Revision ID: 02489f6bcff3
Revises: d0821620cae2
Create Date: 2026-10-20 13:13:59.824926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02489f6bcff3'
down_revision: Union[str, Sequence[str], None] = 'd0821620cae2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
