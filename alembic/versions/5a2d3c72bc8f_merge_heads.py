"""merge heads

Revision ID: 5a2d3c72bc8f
Revises: b62a19c4d801, d0821620cae2
Create Date: 2026-10-20 13:20:06.414488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a2d3c72bc8f'
down_revision: Union[str, Sequence[str], None] = ('b62a19c4d801', 'd0821620cae2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
