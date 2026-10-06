from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from job_aggregator.db.base import Base, TimestampMixin


class Vacancy(TimestampMixin, Base):
    """ORM модель вакансии."""

    __tablename__ = "vacancies"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_vacancies_source_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="hh",
    )
    external_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    area_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    salary_from: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    salary_to: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    salary_currency: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
