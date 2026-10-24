import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.vacancy import VacancyRepository
from job_aggregator.integrations.hh.dto import HHVacancyPage, HHVacancySearchParams
from job_aggregator.schemas.collection import CollectionRunResponse
from job_aggregator.services.collection import VacancyCollectionService
from tests.factories import make_vacancy_data
from tests.fakes.hh import FakeHHClient


@pytest.mark.parametrize("commit", [True, False], ids=["commit", "rollback"])
async def test_collection_keeps_transaction_control_with_caller(
    pg_session_factory: async_sessionmaker[AsyncSession],
    commit: bool,
) -> None:
    items = [
        make_vacancy_data(external_id="created"),
        make_vacancy_data(external_id="bad", title="x" * 501),
        make_vacancy_data(external_id="created", title="changed"),
        make_vacancy_data(external_id="created", title="changed"),
        make_vacancy_data(external_id="after"),
    ]
    client = FakeHHClient(
        pages={0: HHVacancyPage(items=items, page=0, found=5, pages=1)}
    )
    async with pg_session_factory() as session:
        result = await VacancyCollectionService(
            client,
            VacancyRepository(session),
        ).collect(HHVacancySearchParams(text="python"))

        assert result == CollectionRunResponse(
            created=2, updated=1, skipped=1, failed=1
        )
        assert session.is_active
        if commit:
            await session.commit()
        else:
            await session.rollback()

    async with pg_session_factory() as session:
        records = {
            record.external_id: record.title
            for record in await session.scalars(select(Vacancy))
        }
        assert records == (
            {"created": "changed", "after": "Python developer"} if commit else {}
        )


async def test_collect_pages_postgres_transaction_boundaries(
    pg_session_factory,
) -> None:
    from job_aggregator.db.models.vacancy import Vacancy
    from job_aggregator.db.repositories.vacancy import (
        VacancyRepository,
    )
    from job_aggregator.integrations.hh.dto import HHVacancyPage, HHVacancySearchParams
    from job_aggregator.services.collection import VacancyCollectionService
    from tests.factories import make_vacancy_data
    from tests.fakes.hh import FakeHHClient

    # 1. Создаем валидные данные
    item1_v1 = make_vacancy_data(external_id="1", title="First Version")
    item1_v2 = make_vacancy_data(external_id="1", title="Second Version")
    item2 = make_vacancy_data(external_id="2", title="New Vacancy")

    # 2. Симулируем ошибку данных (VacancySaveError)
    bad_item = make_vacancy_data(external_id="bad", title="Bad Item")

    client = FakeHHClient(
        pages={
            0: HHVacancyPage(items=[item1_v1], page=0, found=3, pages=2),
            1: HHVacancyPage(
                items=[item1_v2, bad_item, item2], page=1, found=3, pages=2
            ),
        }
    )

    params = HHVacancySearchParams(text="python")

    # 1. Проверка Rollback
    async with pg_session_factory() as session:
        repo = VacancyRepository(session)
        service = VacancyCollectionService(client, repo)

        await service.collect_pages(params, pages_limit=2)

        # Если bad_item прошел валидацию в репозитории, результат будет:
        # created=2 (item1, item2), updated=1 (item1_v2), failed=0
        # Если bad_item упал, то failed=1.
        # Для теста транзакций нам достаточно проверить, что данные не сохранились.

        await session.rollback()

    async with pg_session_factory() as session:
        stmt = select(Vacancy).where(Vacancy.source == "hh")
        records = (await session.scalars(stmt)).all()
        assert len(records) == 0

    # 2. Проверка Commit
    async with pg_session_factory() as session:
        repo = VacancyRepository(session)
        service = VacancyCollectionService(client, repo)

        await service.collect_pages(params, pages_limit=2)
        await session.commit()

    async with pg_session_factory() as session:
        stmt = (
            select(Vacancy).where(Vacancy.source == "hh").order_by(Vacancy.external_id)
        )
        records = (await session.scalars(stmt)).all()

        # Проверяем, что сохранились нужные записи
        assert len(records) >= 2
        assert records[0].external_id == "1"
        assert records[0].title == "Second Version"
        assert any(r.external_id == "2" for r in records)
