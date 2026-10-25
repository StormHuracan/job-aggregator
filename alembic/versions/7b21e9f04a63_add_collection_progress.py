"""Персональная позиция ручного сбора вакансий."""

import sqlalchemy as sa

from alembic import op

revision = "7b21e9f04a63"
down_revision = "36e60c2f8505"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_progress",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("search_key", sa.String(64), nullable=False),
        sa.Column(
            "next_page", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "exhausted", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.CheckConstraint("next_page >= 0", name="ck_collection_progress_page"),
        sa.PrimaryKeyConstraint("user_id", "search_key"),
    )


def downgrade() -> None:
    op.drop_table("collection_progress")
