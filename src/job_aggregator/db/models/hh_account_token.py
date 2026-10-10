from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, validates

from job_aggregator.db.base import Base, TimestampMixin


class HHAccountToken(TimestampMixin, Base):
    """ORM модель OAuth-токенов HH.ru. Поддерживает только одну актуальную запись."""

    __tablename__ = "hh_account_tokens"

    __table_args__ = (
        UniqueConstraint("singleton", name="uq_hh_account_tokens_singleton"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Всегда True — гарантирует единственность активного набора через unique.
    singleton: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    @validates("access_expires_at")
    def _validate_access_expires_at(
        self, key: str, value: datetime | None
    ) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("access_expires_at must be timezone-aware")
        return value.astimezone(UTC)

    def __repr__(self) -> str:
        return (
            f"HHAccountToken(id={self.id!r}, "
            f"access_expires_at={self.access_expires_at!r})"
        )
