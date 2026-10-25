from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from job_aggregator.db.base import Base


class TelegramBinding(Base):
    __tablename__ = "telegram_bindings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_telegram_bindings_user_id"),
        UniqueConstraint("chat_id", name="uq_telegram_bindings_chat_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_telegram_bindings_user_id_users"),
        nullable=False,
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
