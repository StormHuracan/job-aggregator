from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.saved_search import SavedSearch


class SavedSearchRepository:
    """Репозиторий для чтения активных сохранённых поисков."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled(self) -> list[SavedSearch]:
        """Вернуть активные (is_enabled=True) поиски, отсортированные по id."""
        result = await self._session.scalars(
            select(SavedSearch)
            .where(SavedSearch.is_enabled.is_(True))
            .order_by(SavedSearch.id)
        )
        return list(result)
