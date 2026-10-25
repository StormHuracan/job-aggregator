import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.user import User
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.saved_search_match import SavedSearchMatchRepository
from job_aggregator.db.repositories.vacancy import VacancyRepository
from tests.factories import make_vacancy_data


async def _pair(
    session: AsyncSession,
) -> tuple[int, int]:
    user = User(hh_user_id="hh-1", display_name="Test User")
    session.add(user)
    await session.flush()
    search = SavedSearch(name="Python", text="python", user_id=user.id)
    session.add(search)
    await VacancyRepository(session).upsert(make_vacancy_data(external_id="1"))
    await session.flush()
    vacancy = await session.scalar(select(Vacancy))
    assert vacancy is not None
    await session.commit()
    return search.id, vacancy.id


async def test_concurrent_record_creates_one_pair(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        search_id, vacancy_id = await _pair(session)

    barrier = asyncio.Barrier(2)

    async def save() -> bool:
        async with pg_session_factory() as session:
            repo = SavedSearchMatchRepository(session)
            await barrier.wait()
            created = await repo.record(search_id, vacancy_id)
            await session.commit()
            return created

    results = await asyncio.gather(save(), save())

    assert sorted(results) == [False, True]
    async with pg_session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(SavedSearchMatch))
    assert total == 1


async def test_missing_foreign_key_is_not_a_duplicate(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        search_id, vacancy_id = await _pair(session)
        repo = SavedSearchMatchRepository(session)

        with pytest.raises(IntegrityError):
            await repo.record(999_999, vacancy_id)

        assert await repo.record(search_id, vacancy_id) is True
