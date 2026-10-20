from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates

from job_aggregator.db.base import Base, TimestampMixin


class HHAccount(TimestampMixin, Base):
    """Персональные OAuth-токены HH.ru; значения токенов скрыты в repr."""

    __tablename__ = "hh_accounts"
    __table_args__ = (UniqueConstraint("user_id", name="uq_hh_accounts_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    @validates("access_expires_at")
    def _validate_expiry(self, key: str, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("access_expires_at must be timezone-aware")
        return value.astimezone(UTC)

    def __repr__(self) -> str:
        return f"HHAccount(id={self.id!r}, user_id={self.user_id!r})"
