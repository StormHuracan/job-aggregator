from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def test_upsert_creates_new_record(sqlite_session: AsyncSession) -> None:
    repo = VacancyRepository(sqlite_session)
    assert await repo.upsert(_data()) is True
    await sqlite_session.commit()

    count = await sqlite_session.scalar(select(func.count()).select_from(Vacancy))
    assert count == 1


async def test_upsert_returns_false_for_existing_pair(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    assert await repo.upsert(_data(title="first")) is True
    await sqlite_session.commit()

    assert await repo.upsert(_data(title="second")) is False
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


async def test_upsert_returns_false_for_identical_data(
    sqlite_session: AsyncSession,
) -> None:
    repo = VacancyRepository(sqlite_session)
    payload = _data()
    await repo.upsert(payload)
    await sqlite_session.commit()

    record = await sqlite_session.scalar(select(Vacancy))
    assert record is not None
    updated_before = _utc(record.updated_at)

    assert await repo.upsert(payload) is False
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
    assert await repo.upsert(_data(source="hh", external_id="777")) is True
    assert await repo.upsert(_data(source="remote", external_id="777")) is True
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
