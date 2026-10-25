from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from job_aggregator.db.base import Base


class TelegramBotState(Base):
    __tablename__ = "telegram_bot_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    update_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
