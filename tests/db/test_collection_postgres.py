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
