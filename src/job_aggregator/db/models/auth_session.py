from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from job_aggregator.db.base import Base, TimestampMixin


def _normalize_datetime(key: str, value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{key} must be timezone-aware")
    return value.astimezone(UTC)


class OAuthState(TimestampMixin, Base):
    """Одноразовый hash state для проверки OAuth callback."""

    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @validates("expires_at", "consumed_at")
    def _validate_datetime(self, key: str, value: datetime | None) -> datetime | None:
        return _normalize_datetime(key, value)


class UserSession(TimestampMixin, Base):
    """Серверная пользовательская сессия с hash непрозрачного cookie token."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @validates("expires_at", "revoked_at")
    def _validate_datetime(self, key: str, value: datetime | None) -> datetime | None:
        return _normalize_datetime(key, value)
