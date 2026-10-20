"""Расширить регион сохранённого поиска до 255 символов.

Revision ID: c47e92ab6130
Revises: 5a2d3c72bc8f
"""

import sqlalchemy as sa
from alembic import op

revision: str = "c47e92ab6130"
down_revision: str = "5a2d3c72bc8f"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Привести длину колонки к публичному контракту API."""
    op.alter_column(
        "saved_searches",
        "area",
        existing_type=sa.String(100),
        type_=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Вернуть прежний лимит; длинные значения PostgreSQL отклонит без обрезки."""
    op.alter_column(
        "saved_searches",
        "area",
        existing_type=sa.String(255),
        type_=sa.String(100),
        existing_nullable=True,
    )
