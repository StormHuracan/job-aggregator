import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories import VacancyRepository
from job_aggregator.schemas.vacancy import VacancyData


def _data(**overrides: Any) -> VacancyData:
    base: dict[str, Any] = {
        "source": "hh",
        "external_id": "12345",
        "title": "Python Developer",
        "company_name": "Acme",
        "area_name": "Москва",
        "salary_from": 100_000,
        "salary_to": 200_000,
        "salary_currency": "RUR",
        "description": "Описание",
        "source_url": "https://hh.ru/vacancy/12345",
        "published_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        "raw_data": {"id": "12345"},
    }
    base.update(overrides)
    return VacancyData(**base)


async def test_concurrent_first_insert_preserves_outer_changes(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Две сессии одновременно вставляют одну пару vacancy.

    Каждая сессия перед upsert() добавляет свой SavedSearch. Один из двух
    upsert'ов получит UNIQUE-конфликт на PostgreSQL, поймает IntegrityError
    и откатит только savepoint. Ни один из маркеров SavedSearch не должен
    потеряться, независимо от того, какая сессия проиграла гонку.
    """
    barrier = asyncio.Barrier(2)

    async def worker(title: str) -> None:
        async with pg_session_factory() as session:
            session.add(SavedSearch(name=f"marker-{title}", text="python"))
            await session.flush()

            repo = VacancyRepository(session)
            await barrier.wait()
            await repo.upsert(_data(title=title))
            await session.commit()

    results = await asyncio.gather(
        worker("from s1"),
        worker("from s2"),
        return_exceptions=True,
    )
    for result in results:
        assert not isinstance(result, Exception), result

    async with pg_session_factory() as session:
        vacancy_count = await session.scalar(select(func.count()).select_from(Vacancy))
        assert vacancy_count == 1

        saved_count = await session.scalar(
            select(func.count()).select_from(SavedSearch)
        )
        assert saved_count == 2, (
            "Оба SavedSearch-маркера должны сохраниться: откат "
            "UNIQUE-конфликта в одной сессии не должен отменять изменения "
            "другой сессии"
        )
