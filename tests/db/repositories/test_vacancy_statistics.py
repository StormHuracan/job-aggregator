from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.repositories.vacancy import VacancyRepository
from tests.factories import make_vacancy_data


async def _save(session: AsyncSession, external_id: str, **fields: Any) -> None:
    await VacancyRepository(session).upsert(
        make_vacancy_data(external_id=external_id, **fields)
    )


def _rur(salary_from: int | None, salary_to: int | None) -> dict[str, Any]:
    return {
        "salary_from": salary_from,
        "salary_to": salary_to,
        "salary_currency": "RUR",
    }


async def test_empty_database_gives_zero_statistics(
    sqlite_session: AsyncSession,
) -> None:
    stats = await VacancyRepository(sqlite_session).get_statistics()

    assert stats.total_vacancies == 0
    assert stats.salary_sample_size == 0
    assert stats.average_salary is None
    assert stats.top_areas == []


async def test_average_salary_uses_midpoints_of_rur_ranges(
    sqlite_session: AsyncSession,
) -> None:
    await _save(sqlite_session, "1", **_rur(100_000, 200_000))
    await _save(sqlite_session, "2", **_rur(200_000, 400_000))

    stats = await VacancyRepository(sqlite_session).get_statistics()

    assert stats.salary_sample_size == 2
    assert stats.average_salary == 225000


async def test_odd_range_sum_keeps_fraction(sqlite_session: AsyncSession) -> None:
    await _save(sqlite_session, "1", **_rur(1, 2))

    stats = await VacancyRepository(sqlite_session).get_statistics()

    assert stats.average_salary == 1.5


async def test_zero_salary_is_a_valid_range(sqlite_session: AsyncSession) -> None:
    await _save(sqlite_session, "1", **_rur(0, 0))

    stats = await VacancyRepository(sqlite_session).get_statistics()

    assert stats.salary_sample_size == 1
    assert stats.average_salary == 0.0


async def test_incomplete_foreign_and_inverted_ranges_are_excluded(
    sqlite_session: AsyncSession,
) -> None:
    await _save(sqlite_session, "1", **_rur(100_000, None))
    await _save(
        sqlite_session,
        "2",
        salary_from=1_000,
        salary_to=2_000,
        salary_currency="USD",
    )
    await _save(sqlite_session, "3", **_rur(300_000, 100_000))

    stats = await VacancyRepository(sqlite_session).get_statistics()

    assert stats.total_vacancies == 3
    assert stats.salary_sample_size == 0
    assert stats.average_salary is None


async def test_top_areas_trim_spaces_and_skip_empty_values(
    sqlite_session: AsyncSession,
) -> None:
    await _save(sqlite_session, "1", area_name="Moscow")
    await _save(sqlite_session, "2", area_name="  Moscow  ")
    await _save(sqlite_session, "3", area_name="Moscow", salary_currency="USD")
    await _save(sqlite_session, "4", area_name=None)
    await _save(sqlite_session, "5", area_name="")
    await _save(sqlite_session, "6", area_name="   ")

    stats = await VacancyRepository(sqlite_session).get_statistics()

    assert stats.total_vacancies == 6
    assert stats.top_areas == [("Moscow", 3)]


async def test_top_areas_limit_and_tie_order(sqlite_session: AsyncSession) -> None:
    await _save(sqlite_session, "1", area_name="Kazan")
    await _save(sqlite_session, "2", area_name="Kazan")
    for index, area in enumerate(["Tver", "Omsk", "Sochi", "Perm", "Ufa"], start=3):
        await _save(sqlite_session, str(index), area_name=area)

    stats = await VacancyRepository(sqlite_session).get_statistics()

    assert stats.top_areas == [
        ("Kazan", 2),
        ("Omsk", 1),
        ("Perm", 1),
        ("Sochi", 1),
        ("Tver", 1),
    ]
