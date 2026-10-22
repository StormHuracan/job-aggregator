"""add saved search matches

Revision ID: 36e60c2f8505
Revises: c47e92ab6130
Create Date: 2026-10-21 13:39:38.737713
"""

import sqlalchemy as sa

from alembic import op

revision: str = "36e60c2f8505"
down_revision: str = "c47e92ab6130"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "saved_search_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("saved_search_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["saved_search_id"],
            ["saved_searches.id"],
            name="fk_saved_search_matches_saved_search_id_saved_searches",
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            name="fk_saved_search_matches_vacancy_id_vacancies",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "saved_search_id",
            "vacancy_id",
            name="uq_saved_search_matches_saved_search_id_vacancy_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("saved_search_matches")
