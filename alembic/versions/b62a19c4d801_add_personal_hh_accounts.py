"""Персональные HH-аккаунты без переноса singleton-токенов.

Revision ID: b62a19c4d801
Revises: f31a8b7d4c2e
"""

import sqlalchemy as sa
from alembic import op

revision = "b62a19c4d801"
down_revision = "f31a8b7d4c2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Старое подключение не имеет владельца, поэтому остаётся нетронутым."""
    op.create_table(
        "hh_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", name="uq_hh_accounts_user_id"),
    )


def downgrade() -> None:
    """Удаляет только новую таблицу, вместе с персональными подключениями."""
    op.drop_table("hh_accounts")
