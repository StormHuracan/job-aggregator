import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories import (
    VacancyRepository,
    VacancyUpsertResult,
)
from job_aggregator.db.repositories.vacancy import VacancySaveError
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

    async def worker(title: str) -> VacancyUpsertResult:
        async with pg_session_factory() as session:
            session.add(SavedSearch(name=f"marker-{title}", text="python"))
            await session.flush()

            repo = VacancyRepository(session)
            await barrier.wait()
            result = await repo.upsert(_data(title=title))
            await session.commit()
            return result

    results = await asyncio.gather(
        worker("from s1"),
        worker("from s2"),
        return_exceptions=True,
    )
    for result in results:
        assert not isinstance(result, Exception), result

    assert sorted(result.value for result in results) == sorted(
        [
            VacancyUpsertResult.CREATED.value,
            VacancyUpsertResult.UPDATED.value,
        ]
    )

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


@pytest.mark.parametrize("existing", [False, True], ids=["insert", "update"])
@pytest.mark.parametrize(
    "invalid_fields",
    [{"title": "x" * 501}, {"company_name": None}],
    ids=["data-error", "integrity-error"],
)
async def test_rejected_vacancy_preserves_outer_transaction(
    pg_session_factory: async_sessionmaker[AsyncSession],
    existing: bool,
    invalid_fields: dict[str, Any],
) -> None:
    async with pg_session_factory() as session:
        repo = VacancyRepository(session)
        if existing:
            await repo.upsert(_data(external_id="bad", title="original"))
            await session.commit()

        session.add(SavedSearch(name="outer-marker", text="python"))
        await session.flush()
        await repo.upsert(_data(external_id="before"))

        with pytest.raises(VacancySaveError):
            await repo.upsert(_data(external_id="bad", **invalid_fields))

        assert session.is_active
        await repo.upsert(_data(external_id="after"))
        await session.commit()

    async with pg_session_factory() as session:
        records = {
            record.external_id: record
            for record in await session.scalars(select(Vacancy))
        }
        assert set(records) == (
            {"before", "after", "bad"} if existing else {"before", "after"}
        )
        if existing:
            assert records["bad"].title == "original"
            assert records["bad"].company_name == "Acme"
        assert await session.scalar(select(func.count()).select_from(SavedSearch)) == 1


async def test_unrelated_pending_failure_is_not_a_vacancy_error(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        session.add(SavedSearch(name=None, text="python"))
        with pytest.raises(IntegrityError):
            await VacancyRepository(session).upsert(_data())
        await session.rollback()


async def test_outer_rollback_removes_successful_upserts_after_rejection(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        repo = VacancyRepository(session)
        await repo.upsert(_data(external_id="before"))
        with pytest.raises(VacancySaveError):
            await repo.upsert(_data(external_id="bad", title="x" * 501))
        await repo.upsert(_data(external_id="after"))
        await session.rollback()

    async with pg_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Vacancy)) == 0
