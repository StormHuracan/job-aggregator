from datetime import datetime, timezone

import pytest

from job_aggregator.schemas.vacancy import VacancyData


def test_vacancy_data_creation_with_all_fields() -> None:
    published_at = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    raw_data = {"id": "123", "name": "Python Developer"}

    vacancy = VacancyData(
        source="hh",
        external_id="123",
        title="Python Developer",
        company_name="Example Company",
        area_name="Minsk",
        salary_from=3000,
        salary_to=5000,
        salary_currency="BYN",
        description="Python backend developer",
        source_url="https://hh.ru/vacancy/123",
        published_at=published_at,
        raw_data=raw_data,
    )

    assert vacancy.source == "hh"
    assert vacancy.external_id == "123"
    assert vacancy.title == "Python Developer"
    assert vacancy.company_name == "Example Company"
    assert vacancy.area_name == "Minsk"
    assert vacancy.salary_from == 3000
    assert vacancy.salary_to == 5000
    assert vacancy.salary_currency == "BYN"
    assert vacancy.description == "Python backend developer"
    assert vacancy.source_url == "https://hh.ru/vacancy/123"
    assert vacancy.published_at == published_at
    assert vacancy.raw_data == raw_data


def test_vacancy_data_creation_with_optional_fields_none() -> None:
    vacancy = VacancyData(
        source="hh",
        external_id="123",
        title="Python Developer",
        company_name="Example Company",
        area_name=None,
        salary_from=None,
        salary_to=None,
        salary_currency=None,
        description=None,
        source_url="https://hh.ru/vacancy/123",
        published_at=None,
        raw_data=None,
    )

    assert vacancy.source == "hh"
    assert vacancy.area_name is None
    assert vacancy.salary_from is None
    assert vacancy.salary_to is None
    assert vacancy.salary_currency is None
    assert vacancy.description is None
    assert vacancy.published_at is None
    assert vacancy.raw_data is None


def test_vacancy_data_rejects_naive_published_at() -> None:
    naive_datetime = datetime(2026, 10, 11, 12, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        VacancyData(
            source="hh",
            external_id="123",
            title="Python Developer",
            company_name="Example Company",
            area_name=None,
            salary_from=None,
            salary_to=None,
            salary_currency=None,
            description=None,
            source_url="https://hh.ru/vacancy/123",
            published_at=naive_datetime,
            raw_data=None,
        )
