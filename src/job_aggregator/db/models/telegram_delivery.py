from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from job_aggregator.db.base import Base


class TelegramDelivery(Base):
    __tablename__ = "telegram_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "saved_search_match_id",
            name="uq_telegram_deliveries_saved_search_match_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    saved_search_match_id: Mapped[int] = mapped_column(
        ForeignKey(
            "saved_search_matches.id",
            name="fk_telegram_deliveries_saved_search_match_id",
        ),
        nullable=False,
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
