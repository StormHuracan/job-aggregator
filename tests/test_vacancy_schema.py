from datetime import UTC, datetime
from types import SimpleNamespace

from job_aggregator.schemas.vacancy import VacancyResponse


def test_vacancy_response_from_orm() -> None:
    vacancy = SimpleNamespace(
        id=1,
        source="hh.ru",
        external_id="123456",
        title="Python Developer",
        company_name="Яндекс",
        area_name="Москва",
        salary_from=150000,
        salary_to=250000,
        salary_currency="RUR",
        description="Описание вакансии",
        source_url="https://hh.ru/vacancy/123456",
        published_at=datetime(2026, 10, 6, 12, 0, tzinfo=UTC),
        created_at=datetime(2026, 10, 6, 13, 0, tzinfo=UTC),
        updated_at=datetime(2026, 10, 6, 13, 30, tzinfo=UTC),
    )
    response = VacancyResponse.model_validate(vacancy)
    assert response.id == 1
    assert response.source == "hh.ru"
    assert response.external_id == "123456"
    assert response.title == "Python Developer"
    assert response.company_name == "Яндекс"
    assert response.area_name == "Москва"
    assert response.salary_from == 150000
    assert response.salary_to == 250000
    assert response.salary_currency == "RUR"
    assert response.description == "Описание вакансии"
    assert response.source_url == "https://hh.ru/vacancy/123456"
    assert response.published_at == datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    assert response.created_at == datetime(2026, 10, 6, 13, 0, tzinfo=UTC)
    assert response.updated_at == datetime(2026, 10, 6, 13, 30, tzinfo=UTC)


def test_vacancy_response_with_optional_fields_none() -> None:
    vacancy = SimpleNamespace(
        id=2,
        source="hh.ru",
        external_id="654321",
        title="Junior Python Developer",
        company_name=None,
        area_name=None,
        salary_from=None,
        salary_to=None,
        salary_currency=None,
        description=None,
        source_url="https://hh.ru/vacancy/654321",
        published_at=None,
        created_at=datetime(2026, 10, 6, 13, 0, tzinfo=UTC),
        updated_at=datetime(2026, 10, 6, 13, 30, tzinfo=UTC),
    )
    response = VacancyResponse.model_validate(vacancy)
    assert response.company_name is None
    assert response.area_name is None
    assert response.salary_from is None
    assert response.salary_to is None
    assert response.salary_currency is None
    assert response.description is None
    assert response.published_at is None


def test_vacancy_response_excludes_internal_fields() -> None:
    vacancy = SimpleNamespace(
        id=3,
        source="hh.ru",
        external_id="789012",
        title="Backend Developer",
        company_name="Тестовая компания",
        area_name="Москва",
        salary_from=None,
        salary_to=None,
        salary_currency=None,
        description=None,
        source_url="https://hh.ru/vacancy/789012",
        published_at=None,
        created_at=datetime(2026, 10, 6, 13, 0, tzinfo=UTC),
        updated_at=datetime(2026, 10, 6, 13, 30, tzinfo=UTC),
        raw_data={"salary": 150000, "secret": "data"},
        hh_access_token="super-secret-token",
    )
    response = VacancyResponse.model_validate(vacancy)
    assert "raw_data" not in response.model_dump()
    assert "hh_access_token" not in response.model_dump()
