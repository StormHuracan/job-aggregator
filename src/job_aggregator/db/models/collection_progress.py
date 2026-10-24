from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from job_aggregator.db.base import Base


class CollectionProgress(Base):
    """Позиция ручного обхода HH для владельца и точных параметров поиска."""

    __tablename__ = "collection_progress"
    __table_args__ = (
        CheckConstraint("next_page >= 0", name="ck_collection_progress_page"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    search_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_page: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    exhausted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
