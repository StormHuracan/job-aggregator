import pytest
from sqlalchemy.exc import IntegrityError

from job_aggregator.db.base import Base
from job_aggregator.db.models.vacancy import Vacancy
from job_aggregator.db.session import create_engine_and_factory


@pytest.fixture
async def session():
    engine, factory = create_engine_and_factory("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


def test_vacancy_model_structure() -> None:
    expected_fields = {
        "id",
        "source",
        "external_id",
        "title",
        "company_name",
        "area_name",
        "salary_from",
        "salary_to",
        "salary_currency",
        "description",
        "source_url",
        "published_at",
        "raw_data",
        "created_at",
        "updated_at",
    }

    actual_fields = set(Vacancy.__table__.columns.keys())

    assert actual_fields == expected_fields


def test_create_vacancy() -> None:
    vacancy = Vacancy(
        source="hh",
        external_id="123456",
        title="Python Developer",
        company_name="Some Company",
        source_url="https://hh.ru/vacancy/123456",
    )

    assert vacancy.source == "hh"
    assert vacancy.external_id == "123456"
    assert vacancy.title == "Python Developer"
    assert vacancy.company_name == "Some Company"
    assert vacancy.source_url == "https://hh.ru/vacancy/123456"

    assert vacancy.area_name is None
    assert vacancy.salary_from is None
    assert vacancy.salary_to is None
    assert vacancy.salary_currency is None
    assert vacancy.description is None
    assert vacancy.published_at is None
    assert vacancy.raw_data is None


async def test_vacancy_can_be_saved(session) -> None:
    vacancy = Vacancy(
        source="hh",
        external_id="123456",
        title="Python Developer",
        company_name="Some Company",
        source_url="https://hh.ru/vacancy/123456",
    )

    session.add(vacancy)
    await session.commit()
    await session.refresh(vacancy)

    assert vacancy.id is not None
    assert vacancy.created_at is not None
    assert vacancy.updated_at is not None


async def test_vacancy_source_and_external_id_must_be_unique(session) -> None:
    vacancy_1 = Vacancy(
        source="hh",
        external_id="123456",
        title="Python Developer",
        company_name="Company 1",
        source_url="https://hh.ru/vacancy/123456",
    )

    vacancy_2 = Vacancy(
        source="hh",
        external_id="123456",
        title="Another Python Developer",
        company_name="Company 2",
        source_url="https://hh.ru/vacancy/123456",
    )

    session.add_all([vacancy_1, vacancy_2])

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_same_external_id_allowed_for_different_sources(session) -> None:
    vacancy_1 = Vacancy(
        source="hh",
        external_id="123456",
        title="Python Developer",
        company_name="Company 1",
        source_url="https://hh.ru/vacancy/123456",
    )

    vacancy_2 = Vacancy(
        source="linkedin",
        external_id="123456",
        title="Python Developer",
        company_name="Company 1",
        source_url="https://linkedin.com/jobs/123456",
    )

    session.add_all([vacancy_1, vacancy_2])
    await session.commit()

    assert vacancy_1.id is not None
    assert vacancy_2.id is not None
    assert vacancy_1.id != vacancy_2.id
