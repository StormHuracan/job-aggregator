# import asyncio
# import logging
# from dataclasses import dataclass

# from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# from job_aggregator.composition import build_collection_service
# from job_aggregator.core.config import Settings
# from job_aggregator.db.repositories.saved_search import UserSavedSearchRepository
# from job_aggregator.db.repositories.saved_search_match import SavedSearchMatchRepository
# from job_aggregator.db.repositories.user import UserSettingsRepository
# from job_aggregator.db.repositories.vacancy import (
#     VacancyRepository,
#     VacancyUpsertResult,
# )
# from job_aggregator.integrations.hh.dto import HHVacancySearchParams
# from job_aggregator.schemas.vacancy import VacancyData

# logger = logging.getLogger(__name__)


# @dataclass(frozen=True, slots=True)
# class SearchCollectionResult:
#     search_id: int
#     created: int
#     updated: int
#     skipped: int
#     failed: int
#     new_matches: int
#     succeeded: bool


# @dataclass(frozen=True, slots=True)
# class UserSearchCollectionResult:
#     user_id: int
#     searches: list[SearchCollectionResult]
#     created: int
#     updated: int
#     skipped: int
#     failed: int
#     new_matches: int


# @dataclass(frozen=True, slots=True)
# class _SearchCriteria:
#     search_id: int
#     text: str
#     area: str | None
#     min_salary: int | None
#     max_salary: int | None


# class SavedSearchCollectionService:
#     """Параллельно собирает активные поиски с независимыми транзакциями."""

#     def __init__(
#         self,
#         session_factory: async_sessionmaker[AsyncSession],
#         settings: Settings,
#     ) -> None:
#         self._session_factory = session_factory
#         self._settings = settings

#     async def collect_for_user(self, user_id: int) -> UserSearchCollectionResult:
#         async with self._session_factory() as session:
#             searches = await UserSavedSearchRepository(session).list_enabled_for_user(
#                 user_id
#             )
#             if not searches:
#                 return self._empty_result(user_id)

#             user_settings = await UserSettingsRepository(session).get_or_create(user_id)
#             pages_limit = user_settings.default_pages_limit
#             criteria = [
#                 _SearchCriteria(
#                     search_id=search.id,
#                     text=search.text,
#                     area=search.area,
#                     min_salary=search.min_salary,
#                     max_salary=search.max_salary,
#                 )
#                 for search in searches
#             ]
#             await session.commit()

#         results = await asyncio.gather(
#             *(self._collect_one(user_id, search, pages_limit) for search in criteria)
#         )
#         results.sort(key=lambda result: result.search_id)

#         return UserSearchCollectionResult(
#             user_id=user_id,
#             searches=results,
#             created=sum(result.created for result in results),
#             updated=sum(result.updated for result in results),
#             skipped=sum(result.skipped for result in results),
#             failed=sum(result.failed for result in results),
#             new_matches=sum(result.new_matches for result in results),
#         )

#     async def _collect_one(
#         self,
#         user_id: int,
#         criteria: _SearchCriteria,
#         pages_limit: int,
#     ) -> SearchCollectionResult:
#         new_matches = 0
#         try:
#             async with self._session_factory() as session:
#                 async with session.begin():
#                     # Revalidate ownership and enabled state immediately before
#                     # collection, so a stale initial snapshot cannot start a search.
#                     search = await UserSavedSearchRepository(session).get_for_user(
#                         user_id, criteria.search_id
#                     )
#                     if search is None or not search.is_enabled:
#                         return self._failed_result(criteria.search_id)

#                     async def record_match(
#                         vacancy: VacancyData, _outcome: VacancyUpsertResult
#                     ) -> None:
#                         nonlocal new_matches
#                         if not self._salary_matches(vacancy, criteria):
#                             return

#                         saved_vacancy = await VacancyRepository(
#                             session
#                         ).get_by_external_id(vacancy.source, vacancy.external_id)
#                         if saved_vacancy is None:
#                             raise RuntimeError("Saved vacancy could not be found")

#                         if await SavedSearchMatchRepository(session).record(
#                             criteria.search_id, saved_vacancy.id
#                         ):
#                             new_matches += 1

#                     collector = build_collection_service(
#                         user_id=user_id,
#                         session=session,
#                         session_factory=self._session_factory,
#                         settings=self._settings,
#                         on_saved=record_match,
#                     )
#                     response = await collector.collect_pages(
#                         HHVacancySearchParams(
#                             text=criteria.text,
#                             area=criteria.area,
#                         ),
#                         pages_limit=pages_limit,
#                     )

#             return SearchCollectionResult(
#                 search_id=criteria.search_id,
#                 created=response.created,
#                 updated=response.updated,
#                 skipped=response.skipped,
#                 failed=response.failed,
#                 new_matches=new_matches,
#                 succeeded=True,
#             )
#         except asyncio.CancelledError:
#             raise
#         except Exception:
#             logger.exception(
#                 "Saved-search collection failed: user_id=%d search_id=%d",
#                 user_id,
#                 criteria.search_id,
#             )
#             return self._failed_result(criteria.search_id)

#     @staticmethod
#     def _salary_matches(vacancy: VacancyData, criteria: _SearchCriteria) -> bool:
#         if criteria.min_salary is not None and (
#             vacancy.salary_from is None or vacancy.salary_from < criteria.min_salary
#         ):
#             return False
#         if criteria.max_salary is not None and (
#             vacancy.salary_to is None or vacancy.salary_to > criteria.max_salary
#         ):
#             return False
#         return True

#     @staticmethod
#     def _failed_result(search_id: int) -> SearchCollectionResult:
#         return SearchCollectionResult(
#             search_id=search_id,
#             created=0,
#             updated=0,
#             skipped=0,
#             failed=0,
#             new_matches=0,
#             succeeded=False,
#         )

#     @staticmethod
#     def _empty_result(user_id: int) -> UserSearchCollectionResult:
#         return UserSearchCollectionResult(
#             user_id=user_id,
#             searches=[],
#             created=0,
#             updated=0,
#             skipped=0,
#             failed=0,
#             new_matches=0,
#         )

"""Сбор активных сохранённых поисков пользователя."""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.composition import build_collection_service
from job_aggregator.core.config import Settings
from job_aggregator.db.repositories.saved_search import UserSavedSearchRepository
from job_aggregator.db.repositories.saved_search_match import SavedSearchMatchRepository
from job_aggregator.db.repositories.user import UserSettingsRepository
from job_aggregator.db.repositories.vacancy import (
    VacancyRepository,
    VacancyUpsertResult,
)
from job_aggregator.integrations.hh.dto import HHVacancySearchParams
from job_aggregator.schemas.vacancy import VacancyData

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SearchCollectionResult:
    search_id: int
    created: int
    updated: int
    skipped: int
    failed: int
    new_matches: int
    succeeded: bool


@dataclass(frozen=True, slots=True)
class UserSearchCollectionResult:
    user_id: int
    searches: list[SearchCollectionResult]
    created: int
    updated: int
    skipped: int
    failed: int
    new_matches: int


@dataclass(frozen=True, slots=True)
class _SearchCriteria:
    search_id: int
    text: str
    area: str | None
    min_salary: int | None
    max_salary: int | None


class SavedSearchCollectionService:
    """Параллельно собирает активные поиски с независимыми транзакциями."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        # SQLite supports only one writer at a time. Keep its test runs
        # deterministic while retaining parallel collection on PostgreSQL.
        self._sqlite_lock = asyncio.Lock()

    async def collect_for_user(self, user_id: int) -> UserSearchCollectionResult:
        async with self._session_factory() as session:
            searches = await UserSavedSearchRepository(session).list_enabled_for_user(
                user_id
            )
            if not searches:
                return self._empty_result(user_id)

            user_settings = await UserSettingsRepository(session).get_or_create(user_id)
            pages_limit = user_settings.default_pages_limit
            criteria = [
                _SearchCriteria(
                    search_id=search.id,
                    text=search.text,
                    area=search.area,
                    min_salary=search.min_salary,
                    max_salary=search.max_salary,
                )
                for search in searches
            ]
            await session.commit()

        results = await asyncio.gather(
            *(self._collect_one(user_id, search, pages_limit) for search in criteria)
        )
        results.sort(key=lambda result: result.search_id)

        return UserSearchCollectionResult(
            user_id=user_id,
            searches=results,
            created=sum(result.created for result in results),
            updated=sum(result.updated for result in results),
            skipped=sum(result.skipped for result in results),
            failed=sum(result.failed for result in results),
            new_matches=sum(result.new_matches for result in results),
        )

    async def _collect_one(
        self,
        user_id: int,
        criteria: _SearchCriteria,
        pages_limit: int,
    ) -> SearchCollectionResult:
        bind = self._session_factory.kw.get("bind")
        if bind is not None and bind.dialect.name == "sqlite":
            async with self._sqlite_lock:
                return await self._collect_one_transaction(
                    user_id, criteria, pages_limit
                )
        return await self._collect_one_transaction(user_id, criteria, pages_limit)

    async def _collect_one_transaction(
        self,
        user_id: int,
        criteria: _SearchCriteria,
        pages_limit: int,
    ) -> SearchCollectionResult:
        new_matches = 0
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    # Revalidate ownership and enabled state immediately before
                    # collection, so a stale initial snapshot cannot start a search.
                    search = await UserSavedSearchRepository(session).get_for_user(
                        user_id, criteria.search_id
                    )
                    if search is None or not search.is_enabled:
                        return self._failed_result(criteria.search_id)

                    async def record_match(
                        vacancy: VacancyData, _outcome: VacancyUpsertResult
                    ) -> None:
                        nonlocal new_matches
                        if not self._salary_matches(vacancy, criteria):
                            return

                        saved_vacancy = await VacancyRepository(
                            session
                        ).get_by_external_id(vacancy.source, vacancy.external_id)
                        if saved_vacancy is None:
                            raise RuntimeError("Saved vacancy could not be found")

                        if await SavedSearchMatchRepository(session).record(
                            criteria.search_id, saved_vacancy.id
                        ):
                            new_matches += 1

                    collector = build_collection_service(
                        user_id=user_id,
                        session=session,
                        session_factory=self._session_factory,
                        settings=self._settings,
                        on_saved=record_match,
                    )
                    response = await collector.collect_pages(
                        HHVacancySearchParams(
                            text=criteria.text,
                            area=criteria.area,
                        ),
                        pages_limit=pages_limit,
                    )

            return SearchCollectionResult(
                search_id=criteria.search_id,
                created=response.created,
                updated=response.updated,
                skipped=response.skipped,
                failed=response.failed,
                new_matches=new_matches,
                succeeded=True,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error(
                "Saved-search collection failed: user_id=%d search_id=%d error=%s",
                user_id,
                criteria.search_id,
                type(error).__name__,
            )
            return self._failed_result(criteria.search_id)

    @staticmethod
    def _salary_matches(vacancy: VacancyData, criteria: _SearchCriteria) -> bool:
        if criteria.min_salary is not None and (
            vacancy.salary_from is None or vacancy.salary_from < criteria.min_salary
        ):
            return False
        if criteria.max_salary is not None and (
            vacancy.salary_to is None or vacancy.salary_to > criteria.max_salary
        ):
            return False
        return True

    @staticmethod
    def _failed_result(search_id: int) -> SearchCollectionResult:
        return SearchCollectionResult(
            search_id=search_id,
            created=0,
            updated=0,
            skipped=0,
            failed=0,
            new_matches=0,
            succeeded=False,
        )

    @staticmethod
    def _empty_result(user_id: int) -> UserSearchCollectionResult:
        return UserSearchCollectionResult(
            user_id=user_id,
            searches=[],
            created=0,
            updated=0,
            skipped=0,
            failed=0,
            new_matches=0,
        )
