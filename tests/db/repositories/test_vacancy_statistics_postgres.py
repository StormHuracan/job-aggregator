from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_aggregator.db.models.saved_search import SavedSearch
from job_aggregator.db.models.saved_search_match import SavedSearchMatch
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories.vacancy import VacancyRepository
from tests.factories import make_vacancy_data


async def test_statistics_on_postgres_do_not_multiply_matched_vacancies(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        repo = VacancyRepository(session)
        await repo.upsert(
            make_vacancy_data(
                external_id="1",
                area_name="Москва",
                salary_from=100_000,
                salary_to=200_000,
                salary_currency="RUR",
            )
        )
        await repo.upsert(
            make_vacancy_data(
                external_id="2",
                area_name=" Москва ",
                salary_from=200_000,
                salary_to=400_000,
                salary_currency="RUR",
            )
        )
        await repo.upsert(
            make_vacancy_data(
                external_id="3",
                area_name="Казань",
                salary_from=1_000,
                salary_to=2_000,
                salary_currency="USD",
            )
        )
        await session.flush()

        first_id = await session.scalar(
            select(Vacancy.id).where(Vacancy.external_id == "1")
        )
        searches = [SavedSearch(name=f"s{i}", text="python") for i in range(2)]
        session.add_all(searches)
        await session.flush()
        now = datetime.now(UTC)
        session.add_all(
            SavedSearchMatch(saved_search_id=s.id, vacancy_id=first_id, matched_at=now)
            for s in searches
        )
        await session.commit()

        stats = await repo.get_statistics()

    assert stats.total_vacancies == 3
    assert stats.salary_sample_size == 2
    assert stats.average_salary == 225000
    assert stats.top_areas == [("Москва", 2), ("Казань", 1)]


async def test_average_salary_does_not_overflow_integer_sum(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        repo = VacancyRepository(session)
        await repo.upsert(
            make_vacancy_data(
                external_id="1",
                salary_from=1_500_000_000,
                salary_to=1_600_000_000,
                salary_currency="RUR",
            )
        )
        await session.commit()

        stats = await repo.get_statistics()

    assert stats.salary_sample_size == 1
    assert stats.average_salary == 1_550_000_000.0
