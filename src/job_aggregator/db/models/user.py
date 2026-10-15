from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_aggregator.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """Локальный пользователь, связанный со стабильным идентификатором HH.ru."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    hh_user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    settings: Mapped["UserSettings"] = relationship(
        back_populates="user",
        uselist=False,
    )


class UserSettings(TimestampMixin, Base):
    """Персональные настройки сбора вакансий пользователя."""

    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint(
            "default_pages_limit > 0",
            name="ck_user_settings_default_pages_limit_positive",
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    default_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_pages_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default=text("5"),
    )

    user: Mapped[User] = relationship(back_populates="settings")
