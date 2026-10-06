from sqlalchemy import Boolean, CheckConstraint, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, validates

from job_aggregator.db.base import Base, TimestampMixin


class SavedSearch(TimestampMixin, Base):
    """ORM модель сохранённого поискового запроса."""

    __tablename__ = "saved_searches"

    __table_args__ = (
        CheckConstraint(
            "length(trim(text)) > 0",
            name="ck_saved_searches_text_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    area: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    @validates("text")
    def _validate_text(self, key: str, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped
