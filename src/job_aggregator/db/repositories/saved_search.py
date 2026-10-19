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


class UserSavedSearchRepository:
    """Репозиторий сохранённых поисков, привязанных к владельцу.

    Не позволяет читать или менять поиски другого пользователя.
    Записи без владельца (user_id IS NULL) не возвращаются.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        *,
        name: str,
        text: str,
        area: str | None,
        min_salary: int | None,
        max_salary: int | None,
    ) -> SavedSearch:
        search = SavedSearch(
            user_id=user_id,
            name=name,
            text=text,
            area=area,
            min_salary=min_salary,
            max_salary=max_salary,
            is_enabled=True,
        )
        self._session.add(search)
        await self._session.flush()
        return search

    async def list_for_user(self, user_id: int) -> list[SavedSearch]:
        result = await self._session.scalars(
            select(SavedSearch)
            .where(SavedSearch.user_id == user_id)
            .order_by(SavedSearch.id)
        )
        return list(result)

    async def get_for_user(self, user_id: int, search_id: int) -> SavedSearch | None:
        return await self._session.scalar(
            select(SavedSearch).where(
                SavedSearch.id == search_id,
                SavedSearch.user_id == user_id,
            )
        )

    async def list_enabled_for_user(self, user_id: int) -> list[SavedSearch]:
        result = await self._session.scalars(
            select(SavedSearch)
            .where(
                SavedSearch.user_id == user_id,
                SavedSearch.is_enabled.is_(True),
            )
            .order_by(SavedSearch.id)
        )
        return list(result)

    async def set_enabled(
        self, user_id: int, search_id: int, is_enabled: bool
    ) -> SavedSearch | None:
        search = await self.get_for_user(user_id, search_id)
        if search is None:
            return None
        search.is_enabled = is_enabled
        await self._session.flush()
        return search
