from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.repositories import VacancyRepository, VacancyUpsertResult
from job_aggregator.schemas.vacancy import VacancyData, VacancyListQuery


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


def _query(**filters: Any) -> VacancyListQuery:
    return VacancyListQuery(limit=100, offset=0, **filters)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def test_upsert_creates_new_record(sqlite_session: AsyncSession) -> None:
    repo = VacancyRepository(sqlite_session)
    assert await repo.upsert(_data()) == VacancyUpsertResult.CREATED
    await sqlite_session.commit()

    count = await sqlite_session.scalar(select(func.count()).select_from(Vacancy))
    assert count == 1


async def test_upsert_returns_updated_for_existing_pair(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    assert await repo.upsert(_data(title="first")) == VacancyUpsertResult.CREATED
    await sqlite_session.commit()

    assert await repo.upsert(_data(title="second")) == VacancyUpsertResult.UPDATED
    await sqlite_session.commit()

    count = await sqlite_session.scalar(select(func.count()).select_from(Vacancy))
    assert count == 1

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    assert record.title == "second"


async def test_upsert_preserves_id_and_created_at(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(title="first"))
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    original_id = record.id
    original_created_at = record.created_at

    await repo.upsert(_data(title="second"))
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    assert record.id == original_id
    assert _utc(record.created_at) == _utc(original_created_at)


async def test_upsert_returns_unchanged_for_identical_data(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    payload = _data()
    await repo.upsert(payload)
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    updated_before = _utc(record.updated_at)

    assert await repo.upsert(payload) == VacancyUpsertResult.UNCHANGED
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    assert _utc(record.updated_at) == updated_before


async def test_upsert_updates_updated_at_on_change(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(title="first"))
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    updated_before = _utc(record.updated_at)

    # Сдвигаем время, чтобы разница в updated_at была заметна.
    await repo.upsert(_data(title="second"))
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    assert _utc(record.updated_at) >= updated_before
    assert record.title == "second"


async def test_upsert_clears_nullable_field_when_none(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(area_name="Москва"))
    await sqlite_session.commit()

    await repo.upsert(_data(area_name=None))
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    assert record.area_name is None


async def test_upsert_allows_same_external_id_for_different_sources(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    assert (
        await repo.upsert(_data(source="hh", external_id="777"))
        == VacancyUpsertResult.CREATED
    )

    assert (
        await repo.upsert(_data(source="remote", external_id="777"))
        == VacancyUpsertResult.CREATED
    )
    await sqlite_session.commit()

    count = await sqlite_session.scalar(select(func.count()).select_from(Vacancy))
    assert count == 2


async def test_upsert_does_not_commit(sqlite_session: AsyncSession) -> None:
    """Репозиторий не вызывает session.commit() — коммит делает вызывающий код."""
    repo = VacancyRepository(sqlite_session)

    original_commit = sqlite_session.commit
    commit_called = False

    async def track_commit() -> None:
        nonlocal commit_called
        commit_called = True
        await original_commit()

    sqlite_session.commit = track_commit  # type: ignore[method-assign]
    try:
        await repo.upsert(_data())
        assert commit_called is False
    finally:
        sqlite_session.commit = original_commit  # type: ignore[method-assign]


async def test_list_filters_by_company_case_insensitive(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(external_id="1", company_name="ACME Corp"))
    await repo.upsert(_data(external_id="2", company_name="Other"))

    vacancies, total = await repo.list(_query(company="acme"))

    assert [v.external_id for v in vacancies] == ["1"]
    assert total == 1


async def test_list_filters_by_area_case_insensitive(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(external_id="1", area_name="Saint Petersburg"))
    await repo.upsert(_data(external_id="2", area_name="Moscow"))

    vacancies, total = await repo.list(_query(area="petersburg"))

    assert [v.external_id for v in vacancies] == ["1"]
    assert total == 1


async def test_list_filters_text_by_title_or_description(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(
        _data(external_id="1", title="Python Developer", description="Backend")
    )
    await repo.upsert(
        _data(external_id="2", title="Engineer", description="We use PYTHON")
    )
    await repo.upsert(_data(external_id="3", title="Designer", description="Figma"))

    vacancies, total = await repo.list(_query(text="python"))

    assert sorted(v.external_id for v in vacancies) == ["1", "2"]
    assert total == 2


async def test_list_filters_by_salary_from(sqlite_session: AsyncSession) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(external_id="1", salary_from=150_000))
    await repo.upsert(_data(external_id="2", salary_from=50_000))
    await repo.upsert(_data(external_id="3", salary_from=None))

    vacancies, total = await repo.list(_query(salary_from=100_000))

    assert [v.external_id for v in vacancies] == ["1"]
    assert total == 1


async def test_list_filters_by_salary_to(sqlite_session: AsyncSession) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(external_id="1", salary_to=150_000))
    await repo.upsert(_data(external_id="2", salary_to=250_000))
    await repo.upsert(_data(external_id="3", salary_to=None))

    vacancies, total = await repo.list(_query(salary_to=200_000))

    assert [v.external_id for v in vacancies] == ["1"]
    assert total == 1


async def test_list_combines_filters_with_and(sqlite_session: AsyncSession) -> None:
    repo = VacancyRepository(sqlite_session)
    await repo.upsert(_data(external_id="1", company_name="Acme", area_name="Moscow"))
    await repo.upsert(_data(external_id="2", company_name="Acme", area_name="Kazan"))
    await repo.upsert(_data(external_id="3", company_name="Other", area_name="Moscow"))

    vacancies, total = await repo.list(_query(company="acme", area="moscow"))

    assert [v.external_id for v in vacancies] == ["1"]
    assert total == 1


async def test_list_paginates_and_counts_all_matches(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    for day in range(1, 6):
        await repo.upsert(
            _data(
                external_id=str(day),
                published_at=datetime(2026, 1, day, tzinfo=UTC),
            )
        )

    vacancies, total = await repo.list(VacancyListQuery(limit=2, offset=2))

    assert [v.external_id for v in vacancies] == ["3", "2"]
    assert total == 5


async def test_list_sorts_by_published_at_desc_nulls_last_then_id(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    jan_2 = datetime(2026, 1, 2, tzinfo=UTC)
    await repo.upsert(_data(external_id="a", published_at=jan_2))
    await repo.upsert(_data(external_id="b", published_at=None))
    await repo.upsert(
        _data(external_id="c", published_at=datetime(2026, 1, 3, tzinfo=UTC))
    )
    await repo.upsert(_data(external_id="d", published_at=jan_2))

    vacancies, _ = await repo.list(_query())

    assert [v.external_id for v in vacancies] == ["c", "a", "d", "b"]
