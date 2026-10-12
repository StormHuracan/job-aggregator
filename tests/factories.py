from datetime import UTC, datetime
from typing import Any

from job_aggregator.schemas.hh_token import HHAccountTokenData
from job_aggregator.schemas.vacancy import VacancyData


def make_token_data(
    *,
    access_token: str = "access-1",
    refresh_token: str = "refresh-1",
    access_expires_at: datetime | None = None,
) -> HHAccountTokenData:
    """Создаёт набор токенов; без явной даты используется фиксированный срок."""
    return HHAccountTokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=(
            access_expires_at
            if access_expires_at is not None
            else datetime(2030, 1, 1, tzinfo=UTC)
        ),
    )


def make_vacancy_data(**overrides: Any) -> VacancyData:
    """Создаёт минимальную валидную вакансию с заменой указанных полей."""
    fields = {
        "source": "hh",
        "external_id": "123",
        "title": "Python developer",
        "company_name": "Example",
        "area_name": None,
        "salary_from": None,
        "salary_to": None,
        "salary_currency": None,
        "description": None,
        "source_url": "https://hh.ru/vacancy/123",
        "published_at": datetime(2026, 10, 11, tzinfo=UTC),
        "raw_data": None,
    }
    fields.update(overrides)
    return VacancyData(**fields)
