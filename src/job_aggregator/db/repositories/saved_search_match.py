from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch

_PAIR_CONSTRAINT = "uq_saved_search_matches_saved_search_id_vacancy_id"


class SavedSearchMatchRepository:
    """Совпадения общей вакансии с персональным поиском.

    Методы делают flush(), но не commit()/rollback() переданной сессии.
    Повтор пары ловится в SAVEPOINT, чтобы внешняя транзакция осталась рабочей.
    Ошибка внешнего ключа не маскируется под повтор.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, saved_search_id: int, vacancy_id: int) -> bool:
        """Сохраняет пару поиск-вакансия. True только для новой пары."""
        await self._session.flush()
        if await self._find(saved_search_id, vacancy_id) is not None:
            return False

        try:
            async with self._session.begin_nested():
                self._session.add(
                    SavedSearchMatch(
                        saved_search_id=saved_search_id,
                        vacancy_id=vacancy_id,
                        matched_at=datetime.now(UTC),
                    )
                )
                await self._session.flush()
        except IntegrityError as error:
            if _is_pair_conflict(error):
                return False
            raise
        return True

    async def count_unseen_for_user(self, user_id: int) -> int:
        """Число непросмотренных совпадений поисков этого владельца."""
        total = await self._session.scalar(
            select(func.count())
            .select_from(SavedSearchMatch)
            .join(SavedSearch, SavedSearch.id == SavedSearchMatch.saved_search_id)
            .where(
                SavedSearch.user_id == user_id,
                SavedSearchMatch.seen_at.is_(None),
            )
        )
        return total or 0

    async def mark_seen_for_user(self, user_id: int) -> int:
        """Отмечает непросмотренные совпадения владельца и возвращает их число."""
        result = await self._session.execute(
            update(SavedSearchMatch)
            .where(
                SavedSearchMatch.seen_at.is_(None),
                SavedSearchMatch.saved_search_id.in_(
                    select(SavedSearch.id).where(SavedSearch.user_id == user_id)
                ),
            )
            .values(seen_at=datetime.now(UTC))
        )
        await self._session.flush()
        return result.rowcount or 0

    async def _find(
        self, saved_search_id: int, vacancy_id: int
    ) -> SavedSearchMatch | None:
        return await self._session.scalar(
            select(SavedSearchMatch).where(
                SavedSearchMatch.saved_search_id == saved_search_id,
                SavedSearchMatch.vacancy_id == vacancy_id,
            )
        )


def _is_pair_conflict(error: IntegrityError) -> bool:
    orig = error.orig
    if getattr(orig, "sqlstate", None) != "23505":
        return False
    constraint = getattr(orig, "constraint_name", None)
    return constraint in (None, _PAIR_CONSTRAINT)
