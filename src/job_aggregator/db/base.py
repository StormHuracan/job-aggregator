from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utc_now() -> datetime:
    """Timezone-aware текущее время в UTC. Вычисляется при вызове, не при импорте."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Миксин с created_at / updated_at (timezone-aware, UTC)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )
