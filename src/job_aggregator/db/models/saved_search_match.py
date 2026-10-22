from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from job_aggregator.db.base import Base


class SavedSearchMatch(Base):
    __tablename__ = "saved_search_matches"
    __table_args__ = (
        UniqueConstraint(
            "saved_search_id",
            "vacancy_id",
            name="uq_saved_search_matches_saved_search_id_vacancy_id",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    saved_search_id: Mapped[int] = mapped_column(
        ForeignKey(
            "saved_searches.id",
            name="fk_saved_search_matches_saved_search_id_saved_searches",
        ),
        nullable=False,
    )
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey(
            "vacancies.id",
            name="fk_saved_search_matches_vacancy_id_vacancies",
        ),
        nullable=False,
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
